from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


class CRMStateVerifier:
    """Verifies that AmoCRM lead stage matches the expected stage after an update."""

    async def verify(
        self,
        lead_id: Optional[str],
        expected_status_id: Optional[str],
        amocrm: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Fetch the live CRM record and confirm its status_id matches expected.

        Returns a standard verification dict:
          {success, verification_mode, lead_id, expected_status_id,
           actual_status_id, reason, verified_at}
        """
        if not lead_id or not expected_status_id:
            return {
                "success": True,
                "verification_mode": "crm_state",
                "lead_id": lead_id,
                "expected_status_id": expected_status_id,
                "actual_status_id": None,
                "reason": "skipped_no_lead_id_or_status",
                "verified_at": get_local_now().isoformat(),
            }

        if amocrm is None or not (
            callable(getattr(amocrm, "get_lead", None))
            or callable(getattr(amocrm, "fetch_lead", None))
        ):
            return {
                "success": False,
                "verification_mode": "crm_state",
                "lead_id": lead_id,
                "expected_status_id": expected_status_id,
                "actual_status_id": None,
                "reason": "crm_live_readback_unavailable",
                "verified_at": get_local_now().isoformat(),
            }

        actual_status_id: Optional[str] = None
        error: Optional[str] = None

        if amocrm is not None:
            try:
                lead = await _fetch_crm_lead(amocrm, lead_id)
                actual_status_id = str(lead.get("status_id") or "")
            except Exception as exc:
                error = str(exc)
                logger.warning(f"[CRMStateVerifier] fetch failed for lead {lead_id}: {exc}")

        if not actual_status_id and not error:
            error = "crm_state_missing_from_live_readback"

        matched = actual_status_id == str(expected_status_id) if actual_status_id else None

        if error:
            reason = f"crm_fetch_error: {error}"
            success = False
        elif actual_status_id is None:
            reason = "crm_unavailable_skipped"
            success = True  # non-fatal — no amocrm client injected
        elif matched:
            reason = "crm_state_confirmed"
            success = True
        else:
            reason = f"crm_state_mismatch: expected={expected_status_id} actual={actual_status_id}"
            success = False

        return {
            "success": success,
            "verification_mode": "crm_state",
            "lead_id": lead_id,
            "expected_status_id": expected_status_id,
            "actual_status_id": actual_status_id,
            "reason": reason,
            "verified_at": get_local_now().isoformat(),
        }


async def _fetch_crm_lead(amocrm: Any, lead_id: str) -> Dict[str, Any]:
    """Thin wrapper — handles both sync and async CRM clients."""
    import asyncio

    fetch = getattr(amocrm, "get_lead", None) or getattr(amocrm, "fetch_lead", None)
    if fetch is None:
        return {}
    result = fetch(lead_id)
    if asyncio.iscoroutine(result):
        result = await result
    return result if isinstance(result, dict) else {}


class NotificationOutcomeVerifier:
    async def verify(self, task: Any, execution: Dict[str, Any]) -> Dict[str, Any]:
        group_result = dict(execution.get("group_result") or {})
        dm_result = dict(execution.get("dm_result") or {})
        tool_results = list(execution.get("tool_results") or [])

        group_sent = bool(
            group_result.get("success", execution.get("group_sent", False))
        )
        group_message_id = group_result.get("group_message_id")
        dm_attempted = int(
            dm_result.get("metadata", {}).get(
                "attempted", execution.get("dm_attempted", 0)
            )
            or 0
        )
        dm_delivered_count = int(
            dm_result.get("sent_count", execution.get("dm_sent", 0)) or 0
        )
        dm_failed_count = len(
            dm_result.get("failed_targets", execution.get("dm_failed", [])) or []
        )
        sent_count = int(execution.get("sent_count", 0) or 0)

        action_success, action_reason, failed_actions = verify_tool_results(
            tool_results
        )

        reason = execution.get("reason")
        if not reason:
            if not action_success:
                reason = action_reason
            elif group_sent and dm_failed_count == 0:
                reason = "delivery_confirmed"
            elif group_sent:
                reason = "group_delivered_with_partial_dm_failures"
            else:
                reason = "group_delivery_failed"

        return {
            "task_id": getattr(task, "task_id", "unknown"),
            "success": group_sent and action_success,
            "verification_mode": "notification_delivery",
            "group_sent": group_sent,
            "group_message_id": group_message_id,
            "sent_count": sent_count,
            "dm_attempted": dm_attempted,
            "dm_delivered_count": dm_delivered_count,
            "dm_failed_count": dm_failed_count,
            "action_checked": bool(tool_results),
            "action_success": action_success,
            "failed_actions": failed_actions,
            "reason": reason,
            "verified_at": get_local_now().isoformat(),
        }


class ActionOutcomeVerifier:
    async def verify(self, task: Any, execution: Dict[str, Any]) -> Dict[str, Any]:
        tool_results = list(execution.get("tool_results") or [])
        action_success, reason, failed_actions = verify_tool_results(tool_results)
        return {
            "task_id": getattr(task, "task_id", "unknown"),
            "success": action_success,
            "verification_mode": "tool_action_results",
            "checked_actions": len(tool_results),
            "failed_actions": failed_actions,
            "reason": reason,
            "verified_at": get_local_now().isoformat(),
        }


class LiveActionOutcomeVerifier:
    """Bridge legacy agent tasks to canonical ERP live read-back verifiers."""

    def __init__(self, registry: Any):
        self.registry = registry

    async def verify(self, task: Any, execution: Dict[str, Any]) -> Dict[str, Any]:
        action = dict(execution.get("erp_action") or {})
        if not action:
            return {
                "task_id": getattr(task, "task_id", "unknown"),
                "success": False,
                "verification_mode": "live_readback",
                "reason": "erp_action_missing",
                "verified_at": get_local_now().isoformat(),
            }
        result = await self.registry.verify(action, execution)
        return {
            "task_id": getattr(task, "task_id", "unknown"),
            "success": result.success,
            "verification_mode": "live_readback",
            "source": result.source,
            "expected": result.expected,
            "actual": result.actual,
            "reason": result.reason,
            "verified_at": get_local_now().isoformat(),
        }


def verify_tool_results(
    tool_results: List[Dict[str, Any]],
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    if not tool_results:
        return True, "no_tool_actions_to_verify", []

    failed: List[Dict[str, Any]] = []
    for item in tool_results:
        result = dict(item or {})
        tool_name = str(result.get("tool_name") or "unknown")
        metadata = dict(result.get("metadata") or {})
        success = bool(result.get("success"))

        if tool_name == "amocrm.followup_task":
            success = (
                success
                and bool(metadata.get("task_id"))
                and bool(metadata.get("lead_id"))
            )
        elif tool_name == "amocrm.lead_note":
            success = (
                success
                and bool(metadata.get("note_id"))
                and bool(metadata.get("lead_id"))
            )
        elif tool_name == "amocrm.lead_status":
            success = (
                success
                and bool(metadata.get("lead_id"))
                and bool(metadata.get("status_id"))
            )
        elif tool_name.startswith("airtable."):
            success = success and bool(metadata.get("record_id"))
        elif tool_name.startswith("telegram."):
            success = success and (
                bool(result.get("group_message_id"))
                or bool(result.get("sent_count"))
                or bool(result.get("delivered_to"))
            )

        if not success:
            failed.append(
                {
                    "tool_name": tool_name,
                    "reason": result.get("reason") or "verification_failed",
                    "metadata": metadata,
                }
            )

    if failed:
        return False, "tool_action_verification_failed", failed
    return True, "tool_actions_confirmed", []
