from __future__ import annotations

import asyncio
import datetime
import json
import logging
from html import escape
from typing import Any, Dict, List, Optional

from src.services.core.airtable_sync import AirtableSync
from src.time_utils import get_local_now
from src.settings import settings

logger = logging.getLogger(__name__)


class ClientDeliverySystem:
    """Post-payment delivery orchestration for PM handoff and service checkpoints."""

    JOURNEY_PREFIX = "client_delivery:journey:"
    FOLLOWUP_PREFIX = "client_delivery:followup:"

    FOLLOWUP_DEFINITIONS = (
        {
            "key": "pm_handoff_check",
            "hours": 2,
            "title": "PM handoff nazorati",
            "instruction": "PM loyiha handoffini yopdimi: welcome, scope, deadline va mas'ullarni aniq yozdimi?",
        },
        {
            "key": "kickoff_status_check",
            "hours": 24,
            "title": "Kickoff va status update",
            "instruction": "Mijozga kickoff summary yoki hech bo'lmasa keyingi qadamlar bo'yicha status yuborildimi?",
        },
        {
            "key": "feedback_check",
            "hours": 120,
            "title": "Feedback nazorati",
            "instruction": "Mijozdan oraliq feedback olindimi yoki tasdiq kutilyaptimi? Jimlik bo'lsa o'zingiz update bering.",
        },
        {
            "key": "delivery_gate_check",
            "hours": 240,
            "title": "Qoldiq to'lov va final fayllar",
            "instruction": "Tasdiq yaqin bo'lsa qoldiq to'lovni tekshiring. Qarzdorlik yopilmasdan final paket topshirilmasin.",
        },
        {
            "key": "review_referral_check",
            "hours": 336,
            "title": "Otziv va referral",
            "instruction": "Ish topshirilgan bo'lsa 7-14 kun ichida otziv va referral so'rashni unutmang.",
        },
    )

    def __init__(
        self,
        db: Any,
        *,
        bot_client: Any = None,
        admin_bot: Any = None,
        airtable: Optional[AirtableSync] = None,
    ):
        self.db = db
        self.bot_client = bot_client
        self.admin_bot = admin_bot
        self.airtable = airtable or AirtableSync()

    @classmethod
    def _journey_key(cls, project_id: str) -> str:
        return f"{cls.JOURNEY_PREFIX}{project_id}"

    @classmethod
    def _followup_key(cls, project_id: str, checkpoint_key: str) -> str:
        return f"{cls.FOLLOWUP_PREFIX}{project_id}:{checkpoint_key}"

    @staticmethod
    def _safe_json_load(raw: Any) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(str(raw))
        except Exception:
            return {}

    @staticmethod
    def _format_person_mention(person: Optional[Dict[str, Any]], fallback: str) -> str:
        if not person:
            return fallback
        username = str(person.get("username") or "").strip()
        if username:
            return username if username.startswith("@") else f"@{username}"
        user_id = person.get("user_id")
        name = person.get("name") or fallback
        if user_id:
            return f"<a href='tg://user?id={user_id}'>{escape(str(name))}</a>"
        return escape(str(name))

    @staticmethod
    def _normalize_pm_username(handle: Optional[str]) -> Optional[str]:
        if not handle:
            return None
        handle = str(handle).strip()
        if handle.startswith("@"):
            handle = handle[1:]
        return handle or None

    def _resolve_team_topic(self) -> Optional[int]:
        return (
            settings.TOPIC_TASKS_ID
            or settings.TOPIC_GENERAL_ID
            or settings.TOPIC_KIRIM_ID
            or settings.CRM_TOPIC_ID
        )

    async def _resolve_pm(self, workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        project_fields = workflow.get("project_fields") or {}
        pm_value = project_fields.get("PM") or project_fields.get("Manager")
        pm_handle = AirtableSync.resolve_pm_handle(pm_value) if pm_value else None
        pm_username = self._normalize_pm_username(pm_handle)
        if pm_username:
            pm_user = await self.db.get_user_by_username(pm_username)
            if pm_user:
                return {
                    "user_id": pm_user.get("user_id"),
                    "name": pm_user.get("first_name") or pm_username,
                    "username": pm_user.get("username") or pm_username,
                    "source": "airtable",
                }

        fallback_pm = self.db.get_user_by_role("pm")
        if fallback_pm:
            return {
                "user_id": fallback_pm.get("user_id"),
                "name": fallback_pm.get("name") or "PM",
                "username": fallback_pm.get("username"),
                "source": "role",
            }

        owner_id = getattr(settings, "OWNER_ID", None)
        if owner_id:
            return {"user_id": owner_id, "name": "Owner", "username": None, "source": "owner"}
        return None

    async def _refresh_project(self, project_id: Optional[str]) -> Dict[str, Any]:
        if not project_id:
            return {}
        projects = await asyncio.to_thread(self.airtable.get_projects)
        for project in projects:
            if project.get("id") == project_id:
                fields = project.get("fields", {})
                return {
                    "record_id": project_id,
                    "fields": fields,
                    "project_name": AirtableSync._get_field(fields, "project_name"),
                    "stage": AirtableSync._get_field(fields, "stage"),
                    "payment_status": AirtableSync._get_field(fields, "payment_status"),
                    "manager": AirtableSync._get_field(fields, "manager"),
                    "summary": AirtableSync._get_field(fields, "summary"),
                }
        return {}

    async def _update_airtable_after_payment(self, workflow: Dict[str, Any], pm: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        project_id = workflow.get("project_id")
        project_fields = workflow.get("project_fields") or {}
        current_stage = str(AirtableSync._get_field(project_fields, "stage", "") or "")
        current_stage_lower = current_stage.lower()

        update_fields: Dict[str, Any] = {
            "To'lovlar holati": "Dastlabki to'lov tasdiqlandi",
        }
        if any(token in current_stage_lower for token in ("kelishuv", "brief", "won", "sotuv")) or not current_stage_lower:
            update_fields["Loyiha bosqichi"] = "Briefing"
        if pm and pm.get("name") and not project_fields.get("PM") and not project_fields.get("Manager"):
            update_fields["PM"] = pm.get("name")

        updated = False
        if project_id:
            updated = await asyncio.to_thread(self.airtable.update_project_fields, project_id, update_fields)
        return {"updated": bool(updated), "fields": update_fields}

    async def _send_dm(self, user_id: Optional[int], text: str, *, parse_mode: str = "html") -> bool:
        if not user_id or not self.bot_client:
            return False
        try:
            await self.bot_client.send_message(user_id, text, parse_mode=parse_mode)
            return True
        except Exception as exc:
            logger.warning(f"[DELIVERY] PM DM yuborilmadi ({user_id}): {exc}")
            return False

    async def _send_team(self, text: str, *, topic_id: Optional[int] = None, parse_mode: str = "html") -> bool:
        try:
            if self.admin_bot and getattr(self.admin_bot, "team_group_id", None):
                await self.admin_bot.notify_team(text, topic_id=topic_id, parse_mode=parse_mode)
                return True
            if self.bot_client and settings.TEAM_GROUP_ID:
                await self.bot_client.send_message(
                    settings.TEAM_GROUP_ID,
                    text,
                    reply_to=topic_id,
                    parse_mode=parse_mode,
                )
                return True
        except Exception as exc:
            logger.warning(f"[DELIVERY] Team notification yuborilmadi: {exc}")
        return False

    def _build_handoff_packet(self, lifecycle: Dict[str, Any]) -> str:
        project_name = escape(str(lifecycle.get("project_name") or "Noma'lum loyiha"))
        amount = escape(str(lifecycle.get("amount_raw") or "noma'lum"))
        seller = self._format_person_mention(lifecycle.get("seller"), "seller")
        finance = self._format_person_mention(lifecycle.get("finance_approver"), "finance")
        pm = self._format_person_mention(lifecycle.get("pm"), "PM")
        service_type = escape(str(lifecycle.get("service_type") or "aniqlanmagan"))
        client_group = "ha" if lifecycle.get("client_group_confirmed") else "yo'q"
        summary = escape(str(lifecycle.get("project_summary") or lifecycle.get("source_text") or "")[:220])

        return (
            "<b>PM HANDOFF PACK</b>\n"
            f"📁 Loyiha: <b>{project_name}</b>\n"
            f"💸 Tasdiqlangan kirim: <b>{amount}</b>\n"
            f"🧑‍💼 Sotuvchi: {seller}\n"
            f"💰 Finance: {finance}\n"
            f"👤 PM: {pm}\n"
            f"🛠 Xizmat turi: {service_type}\n"
            f"🚪 Mijoz guruhi ochilgan: <b>{client_group}</b>\n"
            f"📝 Kontekst: <i>{summary or 'kirim xabaridan tashqari alohida izoh topilmadi'}</i>\n\n"
            "<b>Keyingi majburiy qadamlar</b>\n"
            "1. PM welcome va loyiha ritmini yozadi.\n"
            "2. Sotuvchi briefdagi muhim detallarni shu oqimga tushiradi.\n"
            "3. 24 soat ichida mijozga kickoff yoki status update chiqadi."
        )

    async def _schedule_followups(self, lifecycle: Dict[str, Any]) -> int:
        now = get_local_now()
        project_id = lifecycle.get("project_id")
        if not project_id:
            return 0

        count = 0
        for item in self.FOLLOWUP_DEFINITIONS:
            due_at = now + datetime.timedelta(hours=item["hours"])
            payload = {
                "status": "pending",
                "project_id": project_id,
                "project_name": lifecycle.get("project_name"),
                "checkpoint_key": item["key"],
                "checkpoint_title": item["title"],
                "instruction": item["instruction"],
                "pm": lifecycle.get("pm"),
                "seller": lifecycle.get("seller"),
                "finance_approver": lifecycle.get("finance_approver"),
                "source_text": lifecycle.get("source_text"),
                "project_stage": lifecycle.get("project_stage"),
                "team_topic_id": self._resolve_team_topic(),
                "due_at": due_at.isoformat(),
                "created_at": now.isoformat(),
            }
            await self.db.set_state(
                self._followup_key(project_id, item["key"]),
                json.dumps(payload, ensure_ascii=False),
            )
            count += 1
        return count

    def _build_followup_text(self, followup: Dict[str, Any], live_project: Dict[str, Any]) -> str:
        project_name = escape(str(followup.get("project_name") or "Noma'lum loyiha"))
        title = escape(str(followup.get("checkpoint_title") or "Lifecycle checkpoint"))
        instruction = escape(str(followup.get("instruction") or ""))
        pm = self._format_person_mention(followup.get("pm"), "PM")
        seller = self._format_person_mention(followup.get("seller"), "seller")
        stage = escape(str(live_project.get("stage") or followup.get("project_stage") or "noma'lum"))
        payment_status = escape(str(live_project.get("payment_status") or "noma'lum"))
        summary = escape(str(live_project.get("summary") or "")[:180])
        key = str(followup.get("checkpoint_key") or "")

        extra = ""
        if key == "pm_handoff_check":
            extra = "PM welcome, timeline, deliverable va javob ritmini yozganini tasdiqlang."
        elif key == "kickoff_status_check":
            extra = "Mijoz jim bo'lsa ham, 'biz ishlayapmiz' degan qisqa update chiqsin."
        elif key == "feedback_check":
            extra = "Feedback kutilyotgan deliverable bo'lsa, deadline bilan qayta qo'ying."
        elif key == "delivery_gate_check":
            extra = "Qoldiq to'lov bo'lsa final fayllar yoki source paket shoshilinch topshirilmasin."
        elif key == "review_referral_check":
            extra = "Agar loyiha allaqachon topshirilgan bo'lsa, otziv va referral so'rang."

        lines = [
            f"<b>{title}</b>",
            f"📁 Loyiha: <b>{project_name}</b>",
            f"👤 PM: {pm}",
            f"🧑‍💼 Sotuvchi: {seller}",
            f"🔄 Airtable stage: <b>{stage}</b>",
            f"💳 To'lov holati: <b>{payment_status}</b>",
            f"🎯 Vazifa: {instruction}",
        ]
        if extra:
            lines.append(f"💡 Fokus: {extra}")
        if summary:
            lines.append(f"📝 Xulosa: <i>{summary}</i>")
        return "\n".join(lines)

    async def handle_finance_approved(self, workflow: Dict[str, Any], income_record: Dict[str, Any]) -> Dict[str, Any]:
        project_id = workflow.get("project_id")
        if not project_id:
            return {"success": False, "reason": "missing_project"}

        pm = await self._resolve_pm(workflow)
        seller = {
            "user_id": workflow.get("sender_id"),
            "name": workflow.get("sender_name") or "Seller",
            "username": workflow.get("sender_username"),
        }

        lifecycle = {
            "project_id": project_id,
            "project_name": workflow.get("project_name"),
            "income_record_id": income_record.get("id"),
            "amount_raw": workflow.get("amount_raw"),
            "amount_value": workflow.get("amount_value"),
            "currency": workflow.get("currency"),
            "seller": seller,
            "finance_approver": workflow.get("finance_approver"),
            "pm": pm,
            "source_text": workflow.get("source_text"),
            "project_fields": workflow.get("project_fields") or {},
            "service_type": (workflow.get("project_fields") or {}).get("Xizmat turi") or (workflow.get("project_fields") or {}).get("Turi"),
            "project_stage": AirtableSync._get_field(workflow.get("project_fields") or {}, "stage"),
            "project_summary": AirtableSync._get_field(workflow.get("project_fields") or {}, "summary"),
            "requires_client_group": bool(workflow.get("requires_client_group")),
            "client_group_confirmed": bool(workflow.get("client_group_confirmed")),
            "created_at": get_local_now().isoformat(),
            "status": "active",
        }

        airtable_update = await self._update_airtable_after_payment(workflow, pm)
        lifecycle["airtable_update"] = airtable_update
        await self.db.set_state(self._journey_key(project_id), json.dumps(lifecycle, ensure_ascii=False))

        handoff_packet = self._build_handoff_packet(lifecycle)
        pm_dm_sent = await self._send_dm(pm.get("user_id") if pm else None, handoff_packet)
        team_sent = await self._send_team(handoff_packet, topic_id=self._resolve_team_topic())
        followup_count = await self._schedule_followups(lifecycle)

        return {
            "success": True,
            "pm": pm,
            "pm_dm_sent": pm_dm_sent,
            "team_sent": team_sent,
            "followup_count": followup_count,
            "handoff_packet": handoff_packet,
            "airtable_update": airtable_update,
        }

    async def run_due_followups(self, limit: int = 10) -> List[Dict[str, Any]]:
        now = get_local_now()
        pending = await self.db.list_states(prefix=self.FOLLOWUP_PREFIX, limit=200)
        triggered: List[Dict[str, Any]] = []

        for item in pending:
            if len(triggered) >= limit:
                break

            payload = self._safe_json_load(item.get("value"))
            if payload.get("status") != "pending":
                continue

            due_at = payload.get("due_at")
            if not due_at:
                continue
            try:
                if datetime.datetime.fromisoformat(str(due_at).replace("Z", "+00:00")) > now:
                    continue
            except Exception:
                continue

            live_project = await self._refresh_project(payload.get("project_id"))
            text = self._build_followup_text(payload, live_project)
            sent_dm = await self._send_dm((payload.get("pm") or {}).get("user_id"), text)
            sent_team = await self._send_team(text, topic_id=payload.get("team_topic_id"))

            if sent_dm or sent_team:
                payload["status"] = "sent"
                payload["sent_at"] = now.isoformat()
                payload["sent_dm"] = sent_dm
                payload["sent_team"] = sent_team
                await self.db.set_state(item["key"], json.dumps(payload, ensure_ascii=False))
                triggered.append(
                    {
                        "project_id": payload.get("project_id"),
                        "project_name": payload.get("project_name"),
                        "checkpoint_key": payload.get("checkpoint_key"),
                        "sent_dm": sent_dm,
                        "sent_team": sent_team,
                    }
                )

        return triggered

    async def render_delivery_cockpit(self, limit: int = 12) -> str:
        journeys = await self.db.list_states(prefix=self.JOURNEY_PREFIX, limit=limit)
        followups = await self.db.list_states(prefix=self.FOLLOWUP_PREFIX, limit=limit * 5)
        if not journeys:
            return "Delivery cockpit bo'sh. Tasdiqlangan kirimdan keyingi lifecycle hali topilmadi."

        lines = ["<b>Oisha Delivery Cockpit</b>", ""]
        followup_map: Dict[str, List[Dict[str, Any]]] = {}
        for item in followups:
            payload = self._safe_json_load(item.get("value"))
            project_id = str(payload.get("project_id") or "")
            if not project_id:
                continue
            followup_map.setdefault(project_id, []).append(payload)

        for journey_item in journeys:
            lifecycle = self._safe_json_load(journey_item.get("value"))
            project_id = str(lifecycle.get("project_id") or "")
            project_name = escape(str(lifecycle.get("project_name") or "Noma'lum loyiha"))
            pm = self._format_person_mention(lifecycle.get("pm"), "PM")
            amount = escape(str(lifecycle.get("amount_raw") or "noma'lum"))
            lines.append(f"• <b>{project_name}</b> — {amount} — {pm}")

            pending_items = [
                item for item in followup_map.get(project_id, [])
                if item.get("status") == "pending"
            ]
            if pending_items:
                pending_items.sort(key=lambda item: item.get("due_at") or "")
                next_item = pending_items[0]
                due_value = escape(str(next_item.get("due_at") or "noma'lum"))
                lines.append(
                    f"  Keyingi checkpoint: {escape(str(next_item.get('checkpoint_title') or next_item.get('checkpoint_key') or 'checkpoint'))}"
                )
                lines.append(f"  Due: {due_value}")
            else:
                lines.append("  Pending checkpoint yo'q.")

        return "\n".join(lines)
