from __future__ import annotations

import uuid
from typing import Any, Optional

from src.services.erp.action_queue import ActionQueue
from src.services.erp.models import ERPAction, VerificationResult


class CompensationService:
    """Creates the smallest safe action needed to repair a partial failure."""

    def __init__(self, queue: ActionQueue):
        self.queue = queue

    async def enqueue_for_partial_failure(
        self,
        original_action: dict[str, Any],
        verification: VerificationResult,
    ) -> Optional[ERPAction]:
        actual = dict(verification.actual or {})
        if (
            actual.get("calendar_event_exists") is True
            and actual.get("amocrm_task_exists") is False
        ):
            action = ERPAction(
                action_id=f"comp-{uuid.uuid4().hex}",
                workflow_id=str(original_action["workflow_id"]),
                action_type="amocrm.create_meeting_task",
                target="amocrm",
                payload=dict(original_action.get("payload") or {}),
                risk_level="low",
                idempotency_key=(
                    f"compensation:{original_action['action_id']}:amocrm_meeting_task"
                ),
                expected_result={
                    "lead_id": original_action.get("payload", {}).get("lead_id"),
                    "task_exists": True,
                },
            )
        elif (
            actual.get("calendar_event_exists") is False
            and actual.get("amocrm_task_exists") is True
        ):
            action = ERPAction(
                action_id=f"comp-{uuid.uuid4().hex}",
                workflow_id=str(original_action["workflow_id"]),
                action_type="calendar.create_meeting",
                target="calendar",
                payload=dict(original_action.get("payload") or {}),
                risk_level="low",
                idempotency_key=(
                    f"compensation:{original_action['action_id']}:calendar_meeting"
                ),
                expected_result={"calendar_event_exists": True},
            )
        else:
            return None

        created = await self.queue.enqueue(action)
        return action if created else None
