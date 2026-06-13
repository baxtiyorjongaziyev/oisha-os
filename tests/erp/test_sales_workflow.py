from datetime import timedelta

import pytest

from src.database import Database
from src.services.erp.action_queue import ActionQueue
from src.services.erp.identity_resolver import IdentityProfile
from src.services.erp.repository import ERPRepository
from src.services.erp.workflows.sales import SalesStage, SalesWorkflowService
from src.time_utils import get_local_now


@pytest.fixture
async def sales(tmp_path):
    db = Database(str(tmp_path / "sales-workflow.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    service = SalesWorkflowService(repo, ActionQueue(repo))
    yield service
    await db.close()


def verified_identities():
    return (
        IdentityProfile(
            phone="+998901234567",
            telegram_user_id=777,
            amo_contact_id=101,
            name="Farrux",
        ),
        IdentityProfile(
            phone="998901234567",
            telegram_user_id=777,
            amo_contact_id=101,
            name="Farrux aka",
        ),
    )


async def start_sales(sales, *, classification="client"):
    reference, context = verified_identities()
    return await sales.start(
        client_id="client-777",
        lead_id=2001,
        chat_id=777,
        reference_identity=reference,
        context_identity=context,
        classification=classification,
        context_kind="private",
        telegram_messages=[
            {"client_id": "client-777", "text": "Logo kerak"},
            {"client_id": "other-client", "text": "Boshqa mijoz siri"},
        ],
        crm_history=[
            {"client_id": "client-777", "lead_id": 2001, "status": "new"},
            {"client_id": "other-client", "lead_id": 9999, "status": "won"},
        ],
        approved_services=["naming", "logo"],
        approved_prices={"logo": {"min": 5_000_000, "max": 15_000_000}},
    )


@pytest.mark.asyncio
async def test_new_lead_first_reply_uses_verified_client_context_only(sales):
    workflow = await start_sales(sales)

    action = await sales.queue_first_reply(
        workflow["workflow_id"],
        "Assalomu alaykum. Logo bo'yicha ehtiyojingizni aniqlab olamiz.",
    )

    stored = await sales.repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["sales_stage"] == SalesStage.CONTACTED.value
    assert stored["data"]["context"]["telegram_messages"] == [
        {"client_id": "client-777", "text": "Logo kerak"}
    ]
    assert action.action_type == "telegram.send_message"
    assert action.expected_result == {"chat_id": 777, "message_exists": True}


@pytest.mark.asyncio
async def test_proposal_is_blocked_before_qualification(sales):
    workflow = await start_sales(sales)

    with pytest.raises(ValueError, match="proposal_requires_qualified_stage"):
        await sales.queue_proposal(
            workflow["workflow_id"],
            service="logo",
            amount=8_000_000,
            message="Logo paketi: 8 000 000 so'm",
        )


@pytest.mark.asyncio
async def test_meeting_action_requires_calendar_and_amocrm_readback(sales):
    workflow = await start_sales(sales)
    await sales.transition(workflow["workflow_id"], SalesStage.CONTACTED)
    await sales.transition(workflow["workflow_id"], SalesStage.QUALIFIED)

    action = await sales.queue_meeting(
        workflow["workflow_id"],
        summary="Farrux aka bilan ekspert konsultatsiya",
        start_time="2026-06-15T13:00:00+05:00",
        duration_minutes=60,
    )

    assert action.action_type == "calendar.create_meeting"
    assert action.payload["lead_id"] == 2001
    assert action.expected_result["calendar_event_exists"] is True
    assert action.expected_result["amocrm_task_exists"] is True
    stored = await sales.repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["sales_stage"] == SalesStage.EXPERT_MEETING.value


@pytest.mark.asyncio
async def test_overdue_followup_creates_crm_task_and_contact_is_limited(sales):
    workflow = await start_sales(sales)
    await sales.transition(workflow["workflow_id"], SalesStage.CONTACTED)
    await sales.transition(workflow["workflow_id"], SalesStage.QUALIFIED)
    overdue = get_local_now() - timedelta(days=3)

    for index in range(3):
        actions = await sales.queue_overdue_follow_up(
            workflow["workflow_id"],
            due_at=overdue,
            message=f"Follow-up {index + 1}",
        )
        assert {item.action_type for item in actions} == {
            "amocrm.create_task",
            "telegram.send_message",
        }

    fourth = await sales.queue_overdue_follow_up(
        workflow["workflow_id"],
        due_at=overdue,
        message="Follow-up 4",
    )
    assert [item.action_type for item in fourth] == ["amocrm.create_task"]


@pytest.mark.asyncio
async def test_price_and_discount_follow_approved_policy(sales):
    workflow = await start_sales(sales)
    await sales.transition(workflow["workflow_id"], SalesStage.CONTACTED)
    await sales.transition(workflow["workflow_id"], SalesStage.QUALIFIED)

    proposal = await sales.queue_proposal(
        workflow["workflow_id"],
        service="logo",
        amount=8_000_000,
        message="Logo paketi: 8 000 000 so'm",
    )
    assert proposal.payload["amount"] == 8_000_000

    with pytest.raises(ValueError, match="price_outside_approved_range"):
        await sales.queue_proposal(
            workflow["workflow_id"],
            service="logo",
            amount=2_000_000,
            message="Logo paketi: 2 000 000 so'm",
        )
    with pytest.raises(ValueError, match="discount_requires_owner_approval"):
        await sales.queue_discount(
            workflow["workflow_id"],
            discount_percent=10,
            message="10% chegirma",
        )


@pytest.mark.asyncio
async def test_personal_and_family_contexts_are_blocked(sales):
    for classification in ("personal", "family", "oila"):
        with pytest.raises(ValueError, match="non_customer_context"):
            await start_sales(sales, classification=classification)

