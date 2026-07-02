from __future__ import annotations

import datetime
from html import escape
from typing import Any, Dict, List, Optional

from src.agents.sales_agent import SalesAgent
from src.time_utils import get_local_now


class LeadOperatingSystem:
    """24/7 lead control tower for recent dialogs and stalled deals."""

    def __init__(self, controller: Any, db: Optional[Any] = None):
        self.controller = controller
        self.db = db or getattr(controller, "db", None)

    def _get_sales_agent(self) -> Optional[SalesAgent]:
        if not self.controller or not getattr(self.controller, "agent_manager", None):
            return None
        agent = self.controller.agent_manager.get_agent("sales")
        return agent if isinstance(agent, SalesAgent) else None

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime.datetime]:
        if not value:
            return None
        try:
            return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    async def review_recent_active_leads(
        self,
        *,
        limit: int = 12,
        lookback_hours: int = 72,
        execute_actions: bool = True,
    ) -> List[Dict[str, Any]]:
        if not self.db:
            return []

        sales_agent = self._get_sales_agent()
        if not sales_agent:
            return []

        recent_leads = await self.db.get_recent_active_leads(
            hours=lookback_hours, limit=limit
        )
        reviewed: List[Dict[str, Any]] = []

        for lead in recent_leads:
            user_id = int(lead.get("user_id") or 0)
            if not user_id:
                continue

            last_client_message = str(lead.get("last_client_message") or "").strip()
            if not last_client_message:
                continue

            user_info = await self.db.get_user_info(user_id) or {}
            crm_status = "Yangi mijoz"
            phone = lead.get("phone") or user_info.get("phone")
            if phone:
                try:
                    crm_status = await self.controller.crm.get_user_context(phone)
                except Exception:
                    crm_status = "Yangi mijoz"

            last_client_dt = self._parse_dt(lead.get("last_client_message_at"))
            lifecycle_dt = self._parse_dt(lead.get("lifecycle_updated_at"))
            should_execute = execute_actions and (
                lifecycle_dt is None
                or (last_client_dt is not None and lifecycle_dt < last_client_dt)
            )

            context = {
                "user_name": lead.get("first_name")
                or user_info.get("first_name")
                or f"User {user_id}",
                "crm_status": crm_status,
                "phone": phone,
                "service_type": lead.get("service_type")
                or user_info.get("service_type"),
                "business_type": lead.get("business_type")
                or user_info.get("business_type"),
                "user_profile": {
                    **user_info,
                    "brand_name": lead.get("brand_name") or user_info.get("brand_name"),
                    "region": lead.get("region") or user_info.get("region"),
                    "intent": lead.get("intent") or user_info.get("intent"),
                    "meeting_time": lead.get("meeting_time")
                    or user_info.get("meeting_time"),
                    "meeting_status": lead.get("meeting_status")
                    or user_info.get("meeting_status"),
                },
            }

            review = await sales_agent.review_conversation(
                user_id,
                last_client_message,
                context=context,
                execute_actions=should_execute,
            )
            assessment = review.get("assessment", {})

            # 3. Chat Summary yuklash (Infinite Memory)
            chat_summary = await self.db.get_chat_summary(user_id)

            await self.db.update_lead_journey(
                user_id,
                stage=str(assessment.get("stage") or "new_lead"),
                status=str(assessment.get("recommended_status") or "Initial Contact"),
                next_action=str(assessment.get("next_action") or "qualify_need"),
                close_probability=float(assessment.get("close_probability") or 0.0),
                lifecycle_updated_at=get_local_now().isoformat(),
            )

            # 4. Airtable ga xulosani sinxronizatsiya qilish
            if (
                should_execute
                and chat_summary
                and hasattr(self.controller.crm, "airtable")
            ):
                at_client = self.controller.crm.airtable
                client_name = context["user_name"]
                at_client.update_project_fields_by_name(
                    client_name, {"Xulosa": chat_summary}
                )

            reviewed.append(
                {
                    **lead,
                    "crm_status": crm_status,
                    "assessment": assessment,
                    "chat_summary": chat_summary,
                    "action_plan": review.get("action_plan", []),
                    "action_results": review.get("action_results", []),
                    "verification": review.get("verification", {}),
                    "recommended_reply": review.get("recommended_reply", ""),
                    "actions_executed": should_execute,
                }
            )

        reviewed.sort(
            key=lambda item: (
                -float(item.get("assessment", {}).get("close_probability") or 0.0),
                item.get("last_client_message_at") or "",
            ),
            reverse=False,
        )
        reviewed.reverse()
        return reviewed

    async def run_reengagement_cycle(self, limit: int = 10) -> List[Dict[str, Any]]:
        sales_agent = self._get_sales_agent()
        if not sales_agent:
            return []
        return await sales_agent.run_reengagement_cycle(limit=limit)

    async def render_cockpit_report(
        self, *, limit: int = 10, lookback_hours: int = 72
    ) -> str:
        leads = await self.review_recent_active_leads(
            limit=limit,
            lookback_hours=lookback_hours,
            execute_actions=False,
        )
        if not leads:
            return "Lead cockpit bo'sh. Oxirgi aktiv mijoz topilmadi."

        lines = [
            "<b>Oisha Lead Cockpit</b>",
            f"Oxirgi aktiv murojaatlar: <b>{len(leads)}</b> ta",
            "",
        ]
        for lead in leads:
            assessment = lead.get("assessment", {})
            stage = escape(
                str(assessment.get("stage") or lead.get("journey_stage") or "new_lead")
            )
            status = escape(
                str(
                    assessment.get("recommended_status")
                    or lead.get("journey_status")
                    or "Initial Contact"
                )
            )
            next_action = escape(
                str(
                    assessment.get("next_action")
                    or lead.get("journey_next_action")
                    or "qualify_need"
                )
            )
            probability = float(
                assessment.get("close_probability")
                or lead.get("close_probability")
                or 0.0
            )
            client_name = escape(
                str(lead.get("first_name") or f"User {lead.get('user_id')}")
            )
            last_text = escape(str(lead.get("last_client_message") or "")[:90])
            lines.append(
                f"• <b>{client_name}</b> — {stage} / {status} / {int(probability * 100)}%"
            )
            summary = lead.get("chat_summary")
            if summary:
                # Snippet: only first 120 chars for the cockpit
                lines.append(f"  📝 <i>Xulosa: {summary[:120]}...</i>")

            lines.append(f"  Keyingi qadam: {next_action}")
            if last_text:
                lines.append(f"  Oxirgi xabar: {last_text}")
        return "\n".join(lines)
