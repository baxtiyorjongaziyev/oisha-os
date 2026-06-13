import pytest

from src.database import Database
from src.services.erp.action_queue import ActionQueue
from src.services.erp.compensation import CompensationService
from src.services.erp.models import ERPWorkflow, VerificationResult
from src.services.erp.repository import ERPRepository


@pytest.mark.asyncio
async def test_partial_meeting_failure_enqueues_only_missing_crm_compensation(tmp_path):
    db = Database(str(tmp_path / "compensation.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    await repo.create_workflow(
        ERPWorkflow(
            workflow_id="wf-meeting",
            workflow_type="sales",
            entity_type="amocrm_lead",
            entity_id="101",
            correlation_id="corr-meeting",
        )
    )
    queue = ActionQueue(repo)
    service = CompensationService(queue)
    original_action = {
        "action_id": "act-meeting",
        "workflow_id": "wf-meeting",
        "action_type": "calendar.create_meeting",
        "target": "calendar",
        "payload": {
            "lead_id": 101,
            "summary": "Suhbat: Farrux",
            "start_time": "2026-06-14T13:00:00+05:00",
        },
    }
    verification = VerificationResult(
        success=False,
        source="calendar+amocrm",
        expected={"calendar_event_exists": True, "amocrm_task_exists": True},
        actual={"calendar_event_exists": True, "amocrm_task_exists": False},
        reason="calendar_created_amocrm_task_missing",
    )

    compensation = await service.enqueue_for_partial_failure(
        original_action,
        verification,
    )

    assert compensation is not None
    assert compensation.action_type == "amocrm.create_meeting_task"
    assert compensation.payload["lead_id"] == 101
    assert await repo.count_rows("erp_actions") == 1
    await db.close()
