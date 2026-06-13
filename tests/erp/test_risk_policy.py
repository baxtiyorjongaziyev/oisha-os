import pytest

from src.services.core.agent_loop import AgentTask
from src.services.core.agent_policy import AgentPolicyEngine
from src.services.core.auto_reply_gate import evaluate as evaluate_auto_reply
from src.services.erp.risk_policy import ERPRiskPolicy


class _StateDB:
    def __init__(self, state=None):
        self.state = state or {}

    async def get_state(self, key, default=None):
        return self.state.get(key, default)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action_type", "payload"),
    [
        ("negotiation.offer_discount", {"discount_percent": 10}),
        ("finance.refund", {"amount": 1_000_000}),
        ("contract.change_terms", {"term": "payment_delay"}),
    ],
)
async def test_financial_and_contract_actions_require_owner_approval(
    action_type, payload
):
    policy = ERPRiskPolicy(_StateDB({"erp:autonomy_level": "A4"}))

    decision = await policy.evaluate(
        action_type=action_type,
        payload=payload,
        module="sales",
        client_id="lead-1",
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.reason == "owner_approval_required"


@pytest.mark.asyncio
async def test_complaint_is_escalated_to_owner():
    policy = ERPRiskPolicy(_StateDB({"erp:autonomy_level": "A4"}))

    decision = await policy.evaluate(
        action_type="client.reply",
        payload={"message": "Mijoz shikoyat qildi va pulni qaytarishni so'radi"},
        module="sales",
        client_id="lead-2",
    )

    assert decision.allowed is False
    assert decision.escalate is True
    assert decision.reason == "complaint_requires_owner"


@pytest.mark.asyncio
async def test_low_risk_meeting_confirmation_is_allowed_at_a3():
    policy = ERPRiskPolicy(_StateDB({"erp:autonomy_level": "A3"}))

    decision = await policy.evaluate(
        action_type="calendar.confirm_meeting",
        payload={"meeting_id": "event-1"},
        module="calendar",
        client_id="lead-3",
    )

    assert decision.allowed is True
    assert decision.risk_level == "low"
    assert decision.max_autonomy == "A3"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [
        {"erp:kill_switch:global": "true"},
        {"erp:kill_switch:module:sales": "true"},
        {"erp:kill_switch:client:lead-7": "true"},
    ],
)
async def test_global_module_and_client_kill_switches_block_actions(state):
    policy = ERPRiskPolicy(_StateDB({**state, "erp:autonomy_level": "A4"}))

    decision = await policy.evaluate(
        action_type="amocrm.create_task",
        payload={"lead_id": 7},
        module="sales",
        client_id="lead-7",
    )

    assert decision.allowed is False
    assert decision.reason.startswith("kill_switch_active:")


@pytest.mark.asyncio
async def test_owner_approval_allows_high_risk_action_inside_policy():
    policy = ERPRiskPolicy(_StateDB({"erp:autonomy_level": "A2"}))

    decision = await policy.evaluate(
        action_type="negotiation.offer_discount",
        payload={"discount_percent": 5},
        module="sales",
        client_id="lead-8",
        approved=True,
    )

    assert decision.allowed is True
    assert decision.reason == "approved_high_risk_action"


@pytest.mark.asyncio
async def test_core_agent_policy_obeys_global_erp_kill_switch():
    db = _StateDB(
        {
            "erp:kill_switch:global": "true",
            "runtime:userbot_authorized": "true",
        }
    )
    task = AgentTask(
        task_id="task-kill",
        kind="sales_conversion_push",
        goal="create CRM task",
        payload={"target": "crm", "action_type": "amocrm.create_task"},
    )

    decision = await AgentPolicyEngine(db).evaluate_action(task)

    assert decision.allowed is False
    assert decision.reason == "kill_switch_active:global"


@pytest.mark.asyncio
async def test_payload_cannot_spoof_owner_approval():
    db = _StateDB(
        {
            "erp:autonomy_level": "A4",
            "runtime:userbot_authorized": "true",
        }
    )
    task = AgentTask(
        task_id="task-spoof",
        kind="autonomous_negotiation",
        goal="offer discount",
        payload={
            "target": "client",
            "action_type": "negotiation.offer_discount",
            "owner_approved": True,
            "discount_percent": 20,
            "allow_in_quiet_hours": True,
        },
        requested_by="scheduler",
    )

    decision = await AgentPolicyEngine(db).evaluate_action(task)

    assert decision.allowed is False
    assert decision.reason == "owner_approval_required"


@pytest.mark.asyncio
async def test_auto_reply_mention_cannot_bypass_global_kill_switch(monkeypatch):
    monkeypatch.setenv("AUTO_REPLY_MODE", "live")
    db = _StateDB({"erp:kill_switch:global": "true"})

    decision = await evaluate_auto_reply(db, is_mentioned=True, message_text="Oisha")

    assert decision.action == "skip"
    assert decision.reason == "kill_switch_active"
