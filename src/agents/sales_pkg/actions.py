"""
Action planning and execution mixin for SalesAgent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.agents.negotiation_engine import NegotiationEngine
from src.agents.negotiation_reengagement import NegotiationReengagementPlanner
from src.agents.sales_pkg.helpers import SalesFormattingMixin

logger = logging.getLogger(__name__)


class SalesActionsMixin(SalesFormattingMixin):
    """Action planning, execution and re-engagement cycles."""

    async def _sync_meeting_state(self, user_id: Optional[int], meeting_window: Dict[str, str]) -> None:
        if not user_id or not self.db:
            return
        try:
            from src.services.core.meetings.scheduler import TelegramMeetingScheduler
            scheduler = TelegramMeetingScheduler(db=self.db)
            await scheduler.save_meeting_request(
                user_id=user_id,
                meeting_summary=meeting_window.get("summary", "Strategik sessiya"),
                start_iso=meeting_window["start"],
                end_iso=meeting_window["end"],
                status="pending_confirmation",
            )
        except Exception as exc:
            logger.debug("[SALES_AGENT] Failed to sync meeting state: %s", exc)

    async def _build_action_plan(
        self,
        assessment,
        task_description: str,
        user_id: Optional[int],
        lead_id: Optional[int],
        phone: Optional[str] = None,
        name: Optional[str] = None,
        persona: Optional[str] = None,
        meeting_window: Optional[Dict[str, str]] = None,
        ai_reply: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []

        if user_id:
            actions.append(
                {
                    "tool": "update_lead_status",
                    "args": {
                        "user_id": user_id,
                        "status_name": getattr(assessment, "recommended_status", "Interested") or "Interested",
                    },
                    "context_user_id": user_id,
                }
            )

        if user_id and (phone or name):
            actions.append(
                {
                    "tool": "save_lead_info",
                    "args": {
                        "user_id": user_id,
                        "name": name,
                        "phone": phone,
                        "lead_quality": assessment.stage,
                    },
                }
            )

        if lead_id and assessment.recommended_status:
            actions.append(
                {
                    "tool": "update_lead_status",
                    "args": {
                        "lead_id": lead_id,
                        "status_name": assessment.recommended_status,
                        "loss_reason": assessment.objection if assessment.recommended_status == "closed_lost" else None,
                    },
                }
            )

        if lead_id:
            note_text = self._build_lead_note(
                assessment=assessment,
                task_description=task_description,
                user_id=user_id,
                lead_id=lead_id,
                action_plan=actions,
                ai_reply=ai_reply,
                persona=persona,
            )
            actions.append(
                {
                    "tool": "add_lead_note",
                    "args": {
                        "lead_id": lead_id,
                        "text": note_text,
                    },
                }
            )

        if lead_id and assessment.next_action != "archive_lead":
            followup = self._build_followup_payload(assessment, user_id=user_id, lead_id=lead_id)
            actions.append(
                {
                    "tool": "create_followup_task",
                    "args": followup,
                }
            )

        return actions

    async def _execute_actions(self, action_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.executor:
            return [{"tool": a["tool"], "status": "skipped_no_executor"} for a in action_plan]

        results: List[Dict[str, Any]] = []
        for action in action_plan:
            tool_name = action["tool"]
            args = action.get("args", {})
            ctx_uid = action.get("context_user_id")
            try:
                if ctx_uid is not None:
                    res = await self.executor.execute(tool_name, args, context_user_id=ctx_uid)
                else:
                    res = await self.executor.execute(tool_name, args)
                results.append({"tool": tool_name, "status": "success", "result": res})
            except Exception as e:
                logger.error(f"[SALES_AGENT] Tool {tool_name} failed: {e}")
                results.append({"tool": tool_name, "status": "error", "error": str(e)})
        return results

    async def plan_reengagement_targets(self, limit: int = 20) -> List[Dict[str, Any]]:
        planner = NegotiationReengagementPlanner(db=self.db)
        return await planner.plan_targets(limit=limit)

    async def run_reengagement_cycle(self, limit: int = 10) -> List[Dict[str, Any]]:
        planner = NegotiationReengagementPlanner(db=self.db)
        targets = await planner.plan_targets(limit=limit)
        results = []
        for t in targets:
            user_id = t.get("user_id")
            if user_id:
                res = await self.process_task(
                    task_description=t.get("reengagement_prompt", "Re-engagement"),
                    context={"user_id": user_id, "lead_id": t.get("lead_id")},
                )
                results.append({"user_id": user_id, "result": res})
        return results

    async def review_conversation(
        self,
        transcript: str,
        user_id: Optional[int] = None,
        lead_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        assessment = await NegotiationEngine.assess_async(transcript)
        esc_reason = self._detect_escalation(transcript, assessment)
        return {
            "assessment": assessment.to_payload(),
            "escalated": bool(esc_reason),
            "escalation_reason": esc_reason,
            "user_id": user_id,
            "lead_id": lead_id,
        }
