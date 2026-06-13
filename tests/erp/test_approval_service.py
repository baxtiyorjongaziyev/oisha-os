from datetime import timedelta

import pytest

from src.database import Database
from src.services.erp.approval_service import ApprovalService
from src.services.erp.models import ERPAction, ERPWorkflow
from src.services.erp.repository import ERPRepository
from src.time_utils import get_local_now


@pytest.fixture
async def approvals(tmp_path):
    db = Database(str(tmp_path / "approvals.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    await repo.create_workflow(
        ERPWorkflow(
            workflow_id="wf-approval",
            workflow_type="sales",
            entity_type="amocrm_lead",
            entity_id="5001",
            correlation_id="corr-approval",
        )
    )
    await repo.create_action(
        ERPAction(
            action_id="act-approval",
            workflow_id="wf-approval",
            action_type="negotiation.offer_discount",
            target="telegram",
            payload={"discount_percent": 5},
            risk_level="high",
            idempotency_key="approval:discount:5001",
            expected_result={"discount_percent": 5},
        )
    )
    service = ApprovalService(repo)
    yield service
    await db.close()


@pytest.mark.asyncio
async def test_owner_can_approve_pending_action(approvals):
    approval = await approvals.request(
        action_id="act-approval",
        requested_from="owner",
        reason="discount_requires_owner",
        ttl_seconds=300,
    )

    decided = await approvals.approve(approval.approval_id, decided_by="owner-1")

    assert decided.status == "approved"
    assert await approvals.is_approved("act-approval") is True


@pytest.mark.asyncio
async def test_owner_can_reject_pending_action(approvals):
    approval = await approvals.request(
        action_id="act-approval",
        requested_from="owner",
        reason="discount_requires_owner",
        ttl_seconds=300,
    )

    decided = await approvals.reject(
        approval.approval_id,
        decided_by="owner-1",
        reason="Chegirma berilmaydi",
    )

    assert decided.status == "rejected"
    assert await approvals.is_approved("act-approval") is False


@pytest.mark.asyncio
async def test_expired_approval_cannot_execute_action(approvals):
    approval = await approvals.request(
        action_id="act-approval",
        requested_from="owner",
        reason="discount_requires_owner",
        ttl_seconds=300,
    )
    conn = await approvals.repo.db.get_connection()
    await conn.execute(
        "UPDATE erp_approvals SET expires_at = ? WHERE approval_id = ?",
        ((get_local_now() - timedelta(seconds=1)).isoformat(), approval.approval_id),
    )
    await conn.commit()

    with pytest.raises(ValueError, match="approval_expired"):
        await approvals.approve(approval.approval_id, decided_by="owner-1")

    stored = await approvals.get(approval.approval_id)
    assert stored.status == "expired"
    assert await approvals.is_approved("act-approval") is False
