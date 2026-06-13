from datetime import datetime

import pytest

from src.agents.autonomous_sales_agent import AutonomousSalesAgent
from src.agents.negotiation_engine import NegotiationAssessment, NegotiationEngine
from src.database import Database
from src.services.core.meeting_scheduler import MeetingCandidate, TelegramMeetingScheduler
from src.services.erp.action_queue import ActionQueue
from src.services.erp.identity_resolver import IdentityProfile
from src.services.erp.negotiation_context import NegotiationContextBuilder
from src.services.erp.repository import ERPRepository
from src.services.erp.workflows.sales import SalesStage, SalesWorkflowService


@pytest.mark.asyncio
async def test_every_client_message_passes_identity_and_context_guard(tmp_path):
    db = Database(str(tmp_path / "negotiation-e2e.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    sales = SalesWorkflowService(repo, ActionQueue(repo))

    with pytest.raises(ValueError, match="identity_confidence_too_low"):
        await sales.start(
            client_id="client-1",
            lead_id=101,
            chat_id=777,
            reference_identity=IdentityProfile(name="Saidazimxoja"),
            context_identity=IdentityProfile(name="Saidazimxoja aka"),
            classification="client",
            context_kind="private",
        )

    with pytest.raises(ValueError, match="group_membership_unverified"):
        NegotiationContextBuilder().build(
            client_id="client-1",
            lead_id=101,
            chat_id=777,
            reference_identity=IdentityProfile(telegram_user_id=777),
            context_identity=IdentityProfile(telegram_user_id=777),
            classification="client",
            context_kind="group",
            membership_verified=False,
        )

    await db.close()


@pytest.mark.asyncio
async def test_verified_assessment_drops_cross_client_history(monkeypatch):
    captured = {}
    assessment = NegotiationAssessment(
        stage="qualified",
        intent="qualify",
        objection="none",
        urgency="normal",
        sentiment="neutral",
        close_probability=0.4,
        autonomy_mode="autonomous",
        recommended_status="Qualified",
        next_action="qualify_need",
        approval_needed=False,
    )

    async def assess_async(*args, **kwargs):
        captured.update(kwargs)
        return assessment

    monkeypatch.setattr(NegotiationEngine, "assess_async", assess_async)
    await NegotiationEngine.assess_verified(
        "Davom etamiz",
        {
            "client_id": "client-1",
            "lead_id": 101,
            "chat_id": 777,
            "identity_confidence": 1.0,
            "telegram_messages": [
                {"client_id": "client-1", "text": "Bizga logo kerak"},
                {"client_id": "client-2", "text": "Maxfiy boshqa mijoz xabari"},
            ],
            "crm_history": [
                {"client_id": "client-1", "lead_id": 101, "status": "qualified"},
                {"client_id": "client-2", "lead_id": 202, "status": "won"},
            ],
        },
    )

    assert captured["history"] == [{"role": "user", "content": "Bizga logo kerak"}]
    assert captured["context"]["crm_history"] == [
        {"client_id": "client-1", "lead_id": 101, "status": "qualified"}
    ]


@pytest.mark.asyncio
async def test_verified_autonomous_reply_is_enqueued_not_sent_directly(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "verified-agent.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    sales = SalesWorkflowService(repo, ActionQueue(repo))
    workflow = await sales.start(
        client_id="client-777",
        lead_id=2001,
        chat_id=777,
        reference_identity=IdentityProfile(telegram_user_id=777),
        context_identity=IdentityProfile(telegram_user_id=777),
        classification="client",
        context_kind="private",
        telegram_messages=[{"client_id": "client-777", "text": "Logo kerak"}],
        approved_services=["logo"],
        approved_prices={"logo": {"min": 5_000_000, "max": 15_000_000}},
    )
    assessment = NegotiationAssessment(
        stage="new_lead",
        intent="qualify",
        objection="none",
        urgency="normal",
        sentiment="neutral",
        close_probability=0.3,
        autonomy_mode="autonomous",
        recommended_status="Initial Contact",
        next_action="qualify_need",
        approval_needed=False,
    )
    async def assess(*args, **kwargs):
        return assessment

    monkeypatch.setattr(
        "src.agents.autonomous_sales_agent.NegotiationEngine.assess_verified",
        assess,
    )

    async def response(*args, **kwargs):
        return "Assalomu alaykum. Qaysi mahsulot uchun logo kerak?"

    agent = AutonomousSalesAgent(db=db, sales_workflow=sales)
    monkeypatch.setattr(agent, "_generate_response", response)

    result = await agent.handle_verified_incoming(
        workflow_id=workflow["workflow_id"],
        message="Logo kerak",
    )

    stored = await repo.get_workflow(workflow["workflow_id"])
    assert stored["data"]["sales_stage"] == SalesStage.CONTACTED.value
    assert result["queued_actions"][0]["action_type"] == "telegram.send_message"
    assert await repo.count_rows("erp_actions") == 1
    await db.close()


@pytest.mark.asyncio
async def test_verified_meeting_scheduler_queues_calendar_and_amocrm_expectation(tmp_path):
    db = Database(str(tmp_path / "verified-meeting.db"))
    await db.init_instance()
    repo = ERPRepository(db)
    await repo.initialize()
    sales = SalesWorkflowService(repo, ActionQueue(repo))
    workflow = await sales.start(
        client_id="client-777",
        lead_id=2001,
        chat_id=777,
        reference_identity=IdentityProfile(phone="+998901234567"),
        context_identity=IdentityProfile(phone="998901234567"),
        classification="client",
        context_kind="private",
    )
    await sales.transition(workflow["workflow_id"], SalesStage.CONTACTED)
    await sales.transition(workflow["workflow_id"], SalesStage.QUALIFIED)
    scheduler = TelegramMeetingScheduler(
        db=db,
        gcalendar=None,
        sales_workflow=sales,
    )
    candidate = MeetingCandidate(
        summary="Ekspert konsultatsiya",
        start_time=datetime.fromisoformat("2026-06-15T13:00:00+05:00"),
        end_time=datetime.fromisoformat("2026-06-15T14:00:00+05:00"),
        description="",
    )

    action = await scheduler.queue_verified_meeting(workflow["workflow_id"], candidate)

    assert action.action_type == "calendar.create_meeting"
    assert action.expected_result["amocrm_task_exists"] is True
    await db.close()
