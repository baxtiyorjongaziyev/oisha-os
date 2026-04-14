from __future__ import annotations

from typing import Any, Dict

from src.time_utils import get_local_now


class NotificationOutcomeVerifier:
    async def verify(self, task: Any, execution: Dict[str, Any]) -> Dict[str, Any]:
        group_result = dict(execution.get("group_result") or {})
        dm_result = dict(execution.get("dm_result") or {})

        group_sent = bool(group_result.get("success", execution.get("group_sent", False)))
        group_message_id = group_result.get("group_message_id")
        dm_attempted = int(dm_result.get("metadata", {}).get("attempted", execution.get("dm_attempted", 0)) or 0)
        dm_delivered_count = int(dm_result.get("sent_count", execution.get("dm_sent", 0)) or 0)
        dm_failed_count = len(dm_result.get("failed_targets", execution.get("dm_failed", [])) or [])
        sent_count = int(execution.get("sent_count", 0) or 0)

        reason = execution.get("reason")
        if not reason:
            if group_sent and dm_failed_count == 0:
                reason = "delivery_confirmed"
            elif group_sent:
                reason = "group_delivered_with_partial_dm_failures"
            else:
                reason = "group_delivery_failed"

        return {
            "task_id": getattr(task, "task_id", "unknown"),
            "success": group_sent,
            "verification_mode": "notification_delivery",
            "group_sent": group_sent,
            "group_message_id": group_message_id,
            "sent_count": sent_count,
            "dm_attempted": dm_attempted,
            "dm_delivered_count": dm_delivered_count,
            "dm_failed_count": dm_failed_count,
            "reason": reason,
            "verified_at": get_local_now().isoformat(),
        }
