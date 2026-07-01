import asyncio
from unittest.mock import AsyncMock

from src.services.core.agent_loop import AgentTask
from src.services.core.agent_policy import AgentPolicyEngine
from src.services.core.agent_verifier import NotificationOutcomeVerifier, verify_tool_results
from src.services.core.tool_adapters import AmoCRMLeadAdapter


class _FakeDB:
    async def get_state(self, key, default=None):
        if key == "runtime:userbot_authorized":
            return "false"
        return default


def test_tool_result_verifier_requires_real_crm_ids():
    ok, reason, failed = verify_tool_results(
        [
            {
                "tool_name": "amocrm.followup_task",
                "success": True,
                "metadata": {"lead_id": 101, "task_id": 202},
            }
        ]
    )
    assert ok is True
    assert reason == "tool_actions_confirmed"
    assert failed == []

    ok, reason, failed = verify_tool_results(
        [
            {
                "tool_name": "amocrm.followup_task",
                "success": True,
                "metadata": {"lead_id": 101},
            }
        ]
    )
    assert ok is False
    assert reason == "tool_action_verification_failed"
    assert failed[0]["tool_name"] == "amocrm.followup_task"


def test_notification_verifier_fails_when_attached_action_fails():
    verifier = NotificationOutcomeVerifier()
    task = AgentTask(task_id="t1", kind="sales_conversion_push", goal="test")
    execution = {
        "group_result": {"success": True, "group_message_id": 55},
        "dm_result": {"metadata": {"attempted": 0}, "sent_count": 0, "failed_targets": []},
        "tool_results": [
            {
                "tool_name": "amocrm.lead_note",
                "success": True,
                "metadata": {"lead_id": 101},
            }
        ],
    }

    result = asyncio.run(verifier.verify(task, execution))

    assert result["success"] is False
    assert result["reason"] == "tool_action_verification_failed"
    assert result["failed_actions"][0]["tool_name"] == "amocrm.lead_note"


def test_policy_blocks_sensitive_client_message_without_userbot_or_owner():
    policy = AgentPolicyEngine(_FakeDB())
    task = AgentTask(
        task_id="t2",
        kind="autonomous_negotiation",
        goal="reply to client",
        payload={
            "target": "client",
            "message": "Narx va to'lov bo'yicha kelishamiz",
            "confidence": 0.99,
            "allow_in_quiet_hours": True,
        },
        requested_by="scheduler",
    )

    decision = asyncio.run(policy.evaluate_action(task))

    assert decision.allowed is False
    assert decision.reason == "userbot_unavailable_for_client_action"


def test_policy_allows_internal_crm_actions_without_userbot():
    policy = AgentPolicyEngine(_FakeDB())
    task = AgentTask(
        task_id="t3",
        kind="sales_conversion_push",
        goal="create internal CRM tasks",
        payload={"target": "crm", "confidence": 1.0, "allow_in_quiet_hours": True},
        requested_by="scheduler",
    )

    decision = asyncio.run(policy.evaluate_action(task))

    assert decision.allowed is True


def test_amocrm_adapter_extracts_embedded_ids():
    result = {"_embedded": {"tasks": [{"id": 777}]}}

    assert AmoCRMLeadAdapter._extract_embedded_id(result, "tasks") == 777


def test_amocrm_adapter_marks_closed_lead_task_as_blocked():
    amocrm = type("Amo", (), {})()
    amocrm.last_error = "lead_closed_for_tasks"
    amocrm.create_task = AsyncMock(return_value=False)
    adapter = AmoCRMLeadAdapter(amocrm)

    result = asyncio.run(
        adapter.create_followup_task(
            lead_id=46088992,
            text="Oisha-OS Keyingi Qadam",
            complete_till=1781370000,
        )
    )

    assert result.success is False
    assert result.status == "blocked"
    assert result.reason == "lead_closed_for_tasks"
