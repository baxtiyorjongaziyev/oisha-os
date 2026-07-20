from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.database import Database
from src.db.repositories.proposals import ProposalRepository
from src.services.core.evolution_scheduler import EvolutionScheduler
from src.services.core.oisha_self_diagnosis import (
    ImprovementProposal,
    OishaSelfDiagnosis,
)
from src.services.core.self_evolution import SelfEvolutionEngine
from src.services.core.self_improvement import SelfImprovementService


@pytest.fixture
async def proposal_db(tmp_path):
    db = Database(str(tmp_path / "improvements.db"))
    await db.init_db()
    yield db
    await db.close()


def make_proposal(proposal_id: str = "DIAG-ABC123") -> ImprovementProposal:
    return ImprovementProposal(
        id=proposal_id,
        category="error_fix",
        severity="high",
        title="Import xatosi",
        problem="Modul yuklanmadi",
        proposed_solution="Import yo'lini tuzating",
        affected_files=["src/example.py"],
        suggested_agent="Coordinator",
    )


@pytest.mark.asyncio
async def test_failed_agent_action_is_detected_and_secret_is_redacted(
    proposal_db,
    tmp_path,
):
    (tmp_path / "src").mkdir(exist_ok=True)
    await proposal_db.log_agent_action(
        user_id=0,
        action_type="runtime_import",
        data={
            "error": "api_key=very-secret ModuleNotFoundError: No module named 'demo'"
        },
        success=False,
    )
    engine = OishaSelfDiagnosis(db=proposal_db, project_root=str(tmp_path))

    proposals = await engine.diagnose_errors()

    assert len(proposals) == 1
    assert proposals[0].severity == "critical"
    assert "very-secret" not in proposals[0].problem
    assert "[REDACTED]" in proposals[0].evidence["error_sample"]


@pytest.mark.asyncio
async def test_semantic_id_is_stable_across_engine_instances(proposal_db, tmp_path):
    (tmp_path / "src").mkdir(exist_ok=True)
    await proposal_db.log_agent_action(
        user_id=0,
        action_type="sync",
        data={"error": "timeout while calling CRM"},
        success=False,
    )
    first = OishaSelfDiagnosis(db=proposal_db, project_root=str(tmp_path))
    second = OishaSelfDiagnosis(db=proposal_db, project_root=str(tmp_path))

    first_ids = {proposal.id for proposal in await first.run_full_diagnosis()}
    second_ids = {proposal.id for proposal in await second.run_full_diagnosis()}

    assert first_ids == second_ids
    assert all(proposal_id.startswith("DIAG-") for proposal_id in first_ids)


@pytest.mark.asyncio
async def test_repository_rerun_preserves_owner_decision(proposal_db):
    repository = ProposalRepository(proposal_db)
    await repository.init_table()
    proposal = make_proposal()
    await repository.save_proposal(proposal)
    assert await repository.update_proposal_status(
        proposal.id,
        "accepted",
        resolved_by="42",
    )

    proposal.problem = "Yangilangan dalil"
    await repository.save_proposal(proposal)
    saved = await repository.get_proposal(proposal.id)

    assert saved["status"] == "accepted"
    assert saved["problem"] == "Yangilangan dalil"
    assert saved["occurrence_count"] == 2


@pytest.mark.asyncio
async def test_repository_rejects_invalid_or_duplicate_transition(proposal_db):
    repository = ProposalRepository(proposal_db)
    await repository.init_table()
    proposal = make_proposal()
    await repository.save_proposal(proposal)

    with pytest.raises(ValueError):
        await repository.update_proposal_status(proposal.id, "executed_without_review")
    assert not await repository.update_proposal_status("missing", "accepted")
    assert await repository.update_proposal_status(proposal.id, "accepted")
    assert not await repository.update_proposal_status(proposal.id, "accepted")


@pytest.mark.asyncio
async def test_future_deferred_proposal_is_not_actionable(proposal_db):
    repository = ProposalRepository(proposal_db)
    await repository.init_table()
    proposal = make_proposal()
    await repository.save_proposal(proposal)
    assert await repository.update_proposal_status(
        proposal.id,
        "deferred",
        deferred_until="2999-01-01T00:00:00+00:00",
    )

    actionable = await repository.get_proposals(
        statuses=["deferred"],
        actionable_only=True,
    )

    assert actionable == []


@pytest.mark.asyncio
async def test_daily_service_is_restart_safe_and_notifies_once(proposal_db, tmp_path):
    bot = SimpleNamespace(send_message=AsyncMock())
    service = SelfImprovementService(
        proposal_db,
        bot_client=bot,
        owner_id=42,
        project_root=str(tmp_path),
    )
    service.diagnosis.run_full_diagnosis = AsyncMock(return_value=[make_proposal()])

    first = await service.run_diagnosis()
    second_service = SelfImprovementService(
        proposal_db,
        bot_client=bot,
        owner_id=42,
        project_root=str(tmp_path),
    )
    second_service.diagnosis.run_full_diagnosis = AsyncMock(
        return_value=[make_proposal()]
    )
    second = await second_service.run_diagnosis()

    assert not first.skipped
    assert first.notified
    assert second.skipped
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_decision_requires_exact_owner_and_returns_handoff(proposal_db, tmp_path):
    service = SelfImprovementService(
        proposal_db,
        owner_id=42,
        project_root=str(tmp_path),
    )
    await service.ensure_ready()
    await service.repository.save_proposal(make_proposal())

    denied, message, _ = await service.decide("DIAG-ABC123", "accept", actor_id=99)
    accepted, handoff, _ = await service.decide("DIAG-ABC123", "accept", actor_id=42)

    assert not denied
    assert "faqat owner" in message
    assert accepted
    assert "Hali kod yozilmadi" in handoff
    assert (await service.repository.get_proposal("DIAG-ABC123"))[
        "status"
    ] == "accepted"


@pytest.mark.asyncio
async def test_weekly_evolution_only_saves_proposal(proposal_db):
    scheduler = EvolutionScheduler.__new__(EvolutionScheduler)
    scheduler._evolution_engine = SimpleNamespace(
        propose_evolution=AsyncMock(
            return_value={"changes": [{"file": "persona_hub.py"}]}
        )
    )
    scheduler._improvement_service = SimpleNamespace(
        save_ai_evolution_suggestion=AsyncMock(
            return_value=SimpleNamespace(id="DIAG-EVOLVE")
        )
    )

    completed = await scheduler._do_evolution()

    assert completed
    scheduler._improvement_service.save_ai_evolution_suggestion.assert_awaited_once()


def test_self_evolution_path_allowlist_blocks_traversal(tmp_path, monkeypatch):
    safe_file = tmp_path / "src" / "services" / "core" / "persona_hub.py"
    safe_file.parent.mkdir(parents=True)
    safe_file.write_text("PROMPT = 'safe'\n", encoding="utf-8")
    monkeypatch.setenv("OISHA_REPO_DIR", str(tmp_path))
    engine = SelfEvolutionEngine.__new__(SelfEvolutionEngine)
    engine.repo_dir = str(tmp_path)

    assert engine._is_safe_file("persona_hub.py")
    assert engine._is_safe_file("src/services/core/persona_hub.py")
    assert not engine._is_safe_file("../../outside/src/services/core/persona_hub.py")


def test_proposal_card_escapes_untrusted_html():
    proposal = make_proposal()
    proposal.title = "<b>fake</b>"
    proposal.problem = "<script>secret()</script>"

    card = OishaSelfDiagnosis.format_proposal_card(proposal)

    assert "&lt;b&gt;fake&lt;/b&gt;" in card
    assert "<script>" not in card


@pytest.mark.asyncio
async def test_feature_gap_detects_implemented_but_unwired_module(tmp_path):
    module = tmp_path / "src" / "services" / "core" / "voice_agent.py"
    module.parent.mkdir(parents=True)
    module.write_text("class VoiceAgent:\n    pass\n", encoding="utf-8")
    engine = OishaSelfDiagnosis(project_root=str(tmp_path))

    proposals = await engine.diagnose_feature_gaps()

    assert any("AI Voice Agent" in proposal.title for proposal in proposals)
