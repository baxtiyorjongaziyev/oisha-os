import pytest

from src.database import Database
from src.services.erp.models import ERPAction, ERPEvent, ERPWorkflow, VerificationResult
from src.services.erp.repository import ERPRepository, ERP_TABLES


@pytest.fixture
async def repository(tmp_path):
    db = Database(str(tmp_path / "erp.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    yield repo
    await db.close()


@pytest.mark.asyncio
async def test_event_raw_hash_is_idempotent(repository):
    event = ERPEvent(
        event_id="evt-1",
        event_type="telegram.message",
        source="telegram_userbot",
        entity_type="contact",
        entity_id="tg-77",
        occurred_at="2026-06-13T10:00:00+05:00",
        correlation_id="corr-1",
        payload={"text": "Branding kerak"},
        raw_hash="sha256:unique-message",
    )

    assert await repository.record_event(event) is True
    assert await repository.record_event(event) is False
    assert await repository.count_rows("erp_events") == 1


@pytest.mark.asyncio
async def test_database_initialization_creates_every_canonical_erp_table(repository):
    conn = await repository.db.get_connection()
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'erp_%'"
    ) as cursor:
        tables = {str(row[0]) for row in await cursor.fetchall()}

    assert ERP_TABLES <= tables


@pytest.mark.asyncio
async def test_action_idempotency_key_prevents_duplicate_side_effect(repository):
    workflow = ERPWorkflow(
        workflow_id="wf-1",
        workflow_type="sales",
        entity_type="amocrm_lead",
        entity_id="1001",
        correlation_id="corr-1",
    )
    await repository.create_workflow(workflow)
    action = ERPAction(
        action_id="act-1",
        workflow_id=workflow.workflow_id,
        action_type="amocrm.create_task",
        target="amocrm",
        payload={"lead_id": 1001},
        risk_level="low",
        idempotency_key="lead:1001:followup:2026-06-13",
        expected_result={"lead_id": 1001},
    )
    duplicate = ERPAction(
        action_id="act-2",
        workflow_id=workflow.workflow_id,
        action_type=action.action_type,
        target=action.target,
        payload=action.payload,
        risk_level=action.risk_level,
        idempotency_key=action.idempotency_key,
        expected_result=action.expected_result,
    )

    assert await repository.create_action(action) is True
    assert await repository.create_action(duplicate) is False
    assert await repository.count_rows("erp_actions") == 1


@pytest.mark.asyncio
async def test_workflow_rejects_illegal_state_transition(repository):
    workflow = ERPWorkflow(
        workflow_id="wf-transition",
        workflow_type="delivery",
        entity_type="airtable_project",
        entity_id="rec-1",
        correlation_id="corr-transition",
    )
    await repository.create_workflow(workflow)

    assert await repository.transition_workflow(workflow.workflow_id, "planned") is True
    with pytest.raises(ValueError, match="illegal_workflow_transition"):
        await repository.transition_workflow(workflow.workflow_id, "completed")

    stored = await repository.get_workflow(workflow.workflow_id)
    assert stored["status"] == "planned"


@pytest.mark.asyncio
async def test_action_cannot_complete_without_successful_verification(repository):
    workflow = ERPWorkflow(
        workflow_id="wf-verify",
        workflow_type="sales",
        entity_type="amocrm_lead",
        entity_id="1002",
        correlation_id="corr-verify",
    )
    await repository.create_workflow(workflow)
    action = ERPAction(
        action_id="act-verify",
        workflow_id=workflow.workflow_id,
        action_type="amocrm.create_task",
        target="amocrm",
        payload={"lead_id": 1002},
        risk_level="low",
        idempotency_key="lead:1002:task:verify",
        expected_result={"lead_id": 1002, "task_exists": True},
    )
    await repository.create_action(action)

    with pytest.raises(ValueError, match="successful_verification_required"):
        await repository.mark_action_completed(action.action_id)

    await repository.record_verification(
        action.action_id,
        VerificationResult(
            success=True,
            source="amocrm",
            expected={"lead_id": 1002, "task_exists": True},
            actual={"lead_id": 1002, "task_exists": True, "task_id": 77},
            reason="live_readback_confirmed",
        ),
    )

    assert await repository.mark_action_completed(action.action_id) is True
    stored = await repository.get_action(action.action_id)
    assert stored["status"] == "completed"
