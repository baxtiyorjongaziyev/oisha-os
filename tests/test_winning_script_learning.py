"""Synthetic CRM boundaries and real SQLite storage; no live service access."""
import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from src.services.call_analytics.script_evidence import extract_examples, verified_sale
from src.services.call_analytics.script_library import ScriptLibrary
from src.services.call_analytics.winning_script_evolver import WinningScriptEvolver

ANALYSIS = {
    "category": "Mijoz", "rubrik_amal_qiladi": True, "sifat_bahosi": 90,
    "suhbat_oilasi": "Ehtiyoj aniqlash", "servis_yonalishi": "Brending",
    "natija": "tolov_kelishildi", "converted": True,
}
TRANSCRIPT = (
    "[00:01] Sotuvchi: Biznesingizdagi qaysi muammoni hal qilmoqchisiz?\n"
    "[00:05] Mijoz: Bizga logo va qadoq dizayni kerak.\n"
    "[00:10] Sotuvchi: Qaror qilishda siz uchun qaysi mezon muhimroq?"
)


@pytest.fixture
def evolver(tmp_path):
    return WinningScriptEvolver(path=tmp_path / "library.sqlite3")


async def capture(evolver, lead_id=1, call_id=None, analysis=None, occurred_at=None, transcript=TRANSCRIPT):
    return await evolver.evolve_from_call(
        lead_id, "+998901234567", "Synthetic manager", 60, transcript,
        ANALYSIS if analysis is None else analysis,
        call_id=call_id or f"synthetic-{lead_id}",
        occurred_at=int(time.time()) - 100 if occurred_at is None else occurred_at,
    )


def crm(lead_ids, status=142, closed_at=None):
    closed_at = int(time.time()) - 10 if closed_at is None else closed_at
    from types import SimpleNamespace
    leads = {i: {"id": i, "status_id": status, "closed_at": closed_at} for i in lead_ids}
    return SimpleNamespace(get_lead=AsyncMock(side_effect=lambda lead_id: leads[lead_id]))


@pytest.mark.asyncio
async def test_ai_claims_never_publish_without_three_distinct_crm_wins(evolver):
    for i in (1, 2, 3):
        assert await capture(evolver, i)
    assert evolver.current_scripts() == []
    client = crm((1, 2, 3), status=100)
    assert (await evolver.reconcile(client))["updated_scripts"] == 0
    assert evolver.current_scripts() == []
    client = crm((1, 2, 3))
    assert (await evolver.reconcile(client))["updated_scripts"] == 1
    script = evolver.current_scripts()[0]
    assert script["distinct_won_leads"] == 3
    assert script["group"] == "discovery:Brending"
    assert script["payment_verified"] is False
    assert script["examples"][0]["phrases"][0] == "Biznesingizdagi qaysi muammoni hal qilmoqchisiz?"
    assert "notarius" not in evolver.format_current_scripts()


@pytest.mark.asyncio
async def test_duplicate_calls_and_same_lead_do_not_inflate_support(evolver):
    assert await capture(evolver, 1, "first")
    assert await capture(evolver, 1, "first") is None
    for call in ("second", "third", "fourth"):
        await capture(evolver, 1, call)
    await evolver.reconcile(crm((1,)))
    assert evolver.current_scripts() == []


@pytest.mark.asyncio
async def test_versions_change_only_when_evidence_changes_and_retractions_remove_active(evolver):
    for i in (1, 2, 3):
        await capture(evolver, i)
    await evolver.reconcile(crm((1, 2, 3)))
    first = evolver.current_scripts()[0]["version"]
    assert (await evolver.reconcile(crm((1, 2, 3))))["updated_scripts"] == 0
    assert evolver.current_scripts()[0]["version"] == first
    await capture(evolver, 4, analysis={**ANALYSIS, "sifat_bahosi": 95})
    await evolver.reconcile(crm((1, 2, 3, 4)))
    assert evolver.current_scripts()[0]["version"] > first
    await evolver.reconcile(crm((1, 2, 3, 4), status=143))
    assert evolver.current_scripts() == []
    assert len(evolver.library.history("discovery:Brending")) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("patch", [
    {"category": "Jamoa"}, {"rubrik_amal_qiladi": False}, {"suhbat_oilasi": "Boshqa"},
    {"servis_yonalishi": "Boshqa"}, {"sifat_bahosi": 74}, {"sifat_bahosi": "nan"},
    {"sifat_bahosi": True}, {"sifat_bahosi": "not-a-score"}, {"sifat_bahosi": 101},
])
async def test_unusable_or_non_sales_calls_are_not_learning_material(evolver, patch):
    assert await capture(evolver, analysis={**ANALYSIS, **patch}) is None
    assert evolver.library.next_leads() == []


@pytest.mark.asyncio
async def test_unknown_time_and_unattributed_speakers_are_not_guessed(evolver):
    assert await capture(evolver, occurred_at=0) is None
    assert await capture(evolver, occurred_at=int(time.time()) + 100) is None
    assert await capture(evolver, transcript="A: Biznesingizdagi muammoni ayting.\nB: Logo kerak.") is None


def test_crm_proof_rejects_mismatch_missing_time_and_post_sale_calls():
    lead = {"id": 1, "status_id": 142, "closed_at": 100}
    assert verified_sale(lead, 1, 90, 120)
    assert not verified_sale(lead, 2, 90, 120)
    assert not verified_sale(lead, 1, 110, 120)
    assert not verified_sale({"id": 1, "status_id": 142}, 1, 90, 120)
    assert not verified_sale({**lead, "is_deleted": True}, 1, 90, 120)


def test_contacts_redacted_client_utterances_and_sensitive_lines_excluded():
    result = extract_examples(
        "Sotuvchi: Bog'lanish uchun +998901234567 va demo@example.test ishlating.\n"
        "Mijoz: Bu mijozning maxfiy gapi, skriptga kirmasin.\n"
        "Sotuvchi: Sizning password parolingiz juda maxfiy."
    )
    assert result == ["Bog'lanish uchun [kontakt] va [kontakt] ishlating."]


@pytest.mark.asyncio
async def test_crm_failure_does_not_turn_candidate_into_winner(evolver):
    await capture(evolver)
    client = crm((1,))
    client.get_lead.side_effect = RuntimeError("synthetic-private-detail")
    result = await evolver.reconcile(client)
    assert result["errors"] == 1
    assert evolver.current_scripts() == []


def test_stale_crm_evidence_is_not_used(tmp_path):
    library = ScriptLibrary(tmp_path / "store.sqlite3")
    for i in (1, 2, 3):
        library.capture({"call_id": str(i), "lead_id": i, "group_key": "closing:Brending",
                         "score": 90, "occurred_at": 10, "examples": ["Synthetic sales phrase"]})
        library.verify(str(i), True, 100)
    assert library.current(now=200)
    assert library.current(now=100000) == []


@pytest.mark.asyncio
async def test_concurrent_capture_is_idempotent(evolver):
    result = await asyncio.gather(*(capture(evolver) for _ in range(8)))
    assert sum(item is not None for item in result) == 1


@pytest.mark.asyncio
async def test_different_services_and_call_purposes_never_share_examples(evolver):
    for i in (1, 2, 3):
        await capture(evolver, i)
    await capture(evolver, 4, analysis={**ANALYSIS, "servis_yonalishi": "SMM"})
    await capture(evolver, 5, analysis={**ANALYSIS, "suhbat_oilasi": "Shartnoma"})
    await evolver.reconcile(crm((1, 2, 3, 4, 5)))
    scripts = evolver.current_scripts()
    assert len(scripts) == 1
    assert {r["lead_id"] for r in scripts[0]["examples"]} == {1, 2, 3}


@pytest.mark.asyncio
async def test_candidates_survive_restart_and_can_win_later(evolver):
    for i in (1, 2, 3):
        await capture(evolver, i)
    await evolver.reconcile(crm((1, 2, 3), status=100))
    restarted = WinningScriptEvolver(path=evolver.library.path)
    await restarted.reconcile(crm((1, 2, 3)))
    assert restarted.current_scripts()[0]["distinct_won_leads"] == 3


@pytest.mark.asyncio
async def test_failed_lead_does_not_starve_other_candidates(evolver):
    await capture(evolver, 1)
    await capture(evolver, 2)
    client = crm((1, 2))
    client.get_lead.side_effect = RuntimeError("synthetic failure")
    await evolver.reconcile(client, limit=1)
    client.get_lead.assert_awaited_once_with(1)
    assert evolver.library.next_leads(limit=1) == [2]


@pytest.mark.asyncio
async def test_capture_hook_registers_source_timestamp_without_contacts(monkeypatch, tmp_path):
    from src.services.call_analytics.script_learning_hook import capture_script_sample

    path = tmp_path / "hook.sqlite3"
    monkeypatch.setattr("src.services.call_analytics.winning_script_evolver.DEFAULT_LIBRARY", path)
    occurred_at = int(time.time()) - 200
    await capture_script_sample({"created_at": occurred_at}, 1, "hook-call", TRANSCRIPT, ANALYSIS)
    library = ScriptLibrary(path)
    sample = library.samples_for_lead(1)[0]
    assert sample["occurred_at"] == occurred_at
    assert sample["won"] == 0
    assert "caller_phone" not in sample


@pytest.mark.asyncio
async def test_historical_replay_is_bounded_and_does_not_rewrite_crm(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from src.services.call_analytics.script_history import capture_historical_sample

    monkeypatch.setattr("src.services.call_analytics.winning_script_evolver.DEFAULT_LIBRARY", tmp_path / "history.sqlite3")
    # DatabasePool's public SELECT boundary; no application runtime or remote DB.
    db = SimpleNamespace(execute=AsyncMock(return_value=[{"transcript": TRANSCRIPT, "duration_seconds": 60}]))
    analyzer = SimpleNamespace(db=db, _script_history_budget=1, analyze_transcript=AsyncMock(return_value=ANALYSIS))
    note = {"created_at": int(time.time()) - 100}
    await capture_historical_sample(analyzer, note, 1, "historical")
    await capture_historical_sample(analyzer, note, 2, "over-budget")
    analyzer.analyze_transcript.assert_awaited_once()
    assert analyzer._script_history_budget == 0
    restarted = WinningScriptEvolver()
    assert restarted.library.samples_for_lead(1)[0]["call_id"] == "historical"
    analyzer._script_history_budget = 1
    await capture_historical_sample(analyzer, note, 1, "historical")
    assert analyzer.analyze_transcript.await_count == 1
