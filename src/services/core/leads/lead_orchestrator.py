"""
Oisha-OS Lead Orchestrator — Unifies Telethon, AI Qualification, amoCRM, Airtable, and AdminBot.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple
from telethon import Button

from src.api_server import add_activity
from src.services.core.airtable_sync import AirtableSync
from src.services.core.admin_bot import AdminBot
from src.services.core.auto_lead_agent import AutoLeadAgent
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.folder_manager import FolderManager
from src.settings import settings
from src.utils.task_scheduler import task_deadline

logger = logging.getLogger(__name__)


class LeadOrchestrator:
    """Oisha-OS Lead Orchestrator."""

    def __init__(
        self,
        amocrm: AmoCRMSync,
        airtable: AirtableSync,
        auto_lead: AutoLeadAgent,
        admin_bot: AdminBot,
        db: Any = None,
        folder_manager: Optional[FolderManager] = None,
    ):
        self.amocrm = amocrm
        self.airtable = airtable
        self.auto_lead = auto_lead
        self.admin_bot = admin_bot
        self.db = db
        self.folder_manager = folder_manager

    async def _qualify_incoming_lead(self, chat_text: str, name: str) -> Tuple[bool, Dict[str, Any]]:
        add_activity("Lidni Skanerlash", f"{name} murojaati AI orqali tahlil qilinmoqda...", "thinking")
        is_lead, lead_details = await self.auto_lead.qualify_chat(chat_text)
        if not is_lead:
            logger.info(f"👸 [ORCHESTRATOR] Not a qualified lead: {name}")
            add_activity("Lid Rad Etildi", f"{name} murojaati biznes uchun mos emas deb topildi.", "info")
            return False, {}

        add_activity("Lid Tasdiqlandi", f"{name} 'LEAD' deb klasifikatsiya qilindi. Intent: {lead_details.get('intent', 'WARM')}", "success")
        return True, lead_details

    async def _sync_with_amocrm(
        self, name: str, phone: Optional[str], user_id: int, username: Optional[str],
        source: str, lead_details: Dict[str, Any]
    ) -> Tuple[Optional[int], bool]:
        intent = lead_details.get("intent", "WARM")
        summary = lead_details.get("summary", "No summary provided")
        extracted_phone = lead_details.get("phone") or phone
        tg_link = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"

        extra_fields = {}
        if settings.AMOCRM_TG_CHAT_FIELD_ID:
            extra_fields[settings.AMOCRM_TG_CHAT_FIELD_ID] = tg_link

        note_content = f"👸 Oisha AI Tahlili (v5.0):\n──────────────────────\n🎯 Intent: {intent}\n📝 Xulosa: {summary}\n📲 Chat: {tg_link}\n📅 Manba: {source}"
        existing = await self.amocrm.get_contact_by_phone(extracted_phone) if (extracted_phone and extracted_phone != "Raqam yo'q") else None

        if existing:
            lead_id = await self._handle_existing_crm_contact(existing["id"], name, extra_fields, note_content)
            is_repeat = True
        else:
            lead_id = await self.amocrm.create_lead(
                name=f"{name} ({intent})", price=0, phone=extracted_phone or "Raqam yo'q",
                note=note_content, extra_fields=extra_fields,
            )
            is_repeat = False

        if lead_id and isinstance(lead_id, int):
            await self.amocrm.create_task(
                element_id=lead_id,
                text=f"Yangi {intent} murojaat! {'(Mavjud mijoz)' if is_repeat else ''} Bog'laning: {name}",
                complete_till=task_deadline(due_in_hours=1),
            )
        return lead_id, is_repeat

    async def _handle_existing_crm_contact(
        self, contact_id: int, name: str, extra_fields: Dict[str, Any], note_content: str
    ) -> Optional[int]:
        active_leads = await self.amocrm.get_active_leads_for_contact(contact_id)
        if active_leads:
            lead_id = active_leads[0]["id"]
            await self.amocrm.add_lead_note(lead_id, note_content)
            await self.amocrm.add_lead_tag(lead_id, "TAKRORIY_MUROJAAT")
            return lead_id
        lead_id = await self.amocrm.create_lead_for_contact(contact_id=contact_id, name=f"{name} (Yangilangan)", price=0, extra_fields=extra_fields)
        if lead_id:
            await self.amocrm.add_lead_note(lead_id, note_content)
            await self.amocrm.add_lead_tag(lead_id, "ESKI_MIJOZ_RE_ENGAGEMENT")
        return lead_id

    async def _resolve_assigned_manager(self) -> Tuple[Optional[int], str]:
        managers = settings.SALES_MANAGER_IDS
        if not managers and self.db:
            db_mgrs = await self.db.get_state("sales_managers", "")
            if db_mgrs:
                managers = [int(i) for i in db_mgrs.split(",") if i]

        dist_mode = await self.db.get_state("lead_distribution_mode", settings.LEAD_DISTRIBUTION_MODE) if self.db else "MANUAL"
        assigned_mgr_id = None
        dist_text = ""

        if dist_mode == "ROUND_ROBIN" and managers:
            last_idx = int(await self.db.get_state("last_manager_idx", -1))
            new_idx = (last_idx + 1) % len(managers)
            assigned_mgr_id = managers[new_idx]
            await self.db.set_state("last_manager_idx", new_idx)
            dist_text = f"🔄 *Taqsimot:* Round Robin -> Menejer ID: `{assigned_mgr_id}`"
        elif dist_mode == "LOAD_BALANCED" and managers:
            dist_text = "⚖️ *Taqsimot:* Load Balanced"
        return assigned_mgr_id, dist_text

    async def _notify_team_and_escalate(
        self, name: str, username: Optional[str], user_id: int, phone: Optional[str],
        source: str, lead_details: Dict[str, Any], lead_id: Optional[int], is_repeat: bool,
        assigned_manager_id: Optional[int], distribution_text: str
    ) -> None:
        if not self.admin_bot.team_group_id:
            return

        intent = lead_details.get("intent", "WARM")
        status_icon = "🔥" if intent == "HOT" else "📋"
        buttons = []

        if assigned_manager_id:
            buttons.append([Button.inline("🤝 Qabul qildim", data=f"accept_lead:{lead_id}:{user_id}:{assigned_manager_id}")])
        else:
            buttons.append([Button.inline("🙋‍♂️ Men olaman", data=f"claim_lead:{lead_id}:{user_id}")])

        phone_label = phone or "Noma'lum"
        card = (
            f"{status_icon} <b>YANGI LID ANIQLANDI!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Mijoz:</b> {name} (@{username or 'yoq'})\n"
            f"📞 <b>Tel:</b> {phone_label}\n"
            f"🎯 <b>Niyat:</b> {intent}\n"
            f"📍 <b>Manba:</b> {source}\n"
            f"📝 <b>Xulosa:</b> {lead_details.get('summary', 'Yoq')}\n"
        )
        if distribution_text:
            card += f"{distribution_text}\n"

        sent_msg = await self.admin_bot.bot_client.send_message(
            self.admin_bot.team_group_id, card, buttons=buttons, parse_mode="html",
        )
        if assigned_manager_id:
            asyncio.create_task(self._start_escalation_timer(lead_id, assigned_manager_id, sent_msg.id))

    async def _start_escalation_timer(self, lead_id: Optional[int], manager_id: int, msg_id: int) -> None:
        await asyncio.sleep(900)  # 15 min escalation
        if self.db:
            claimed = await self.db.get_state(f"lead_claimed_{lead_id}", "false")
            if claimed == "false":
                await self.admin_bot.bot_client.send_message(
                    self.admin_bot.team_group_id,
                    f"⚠️ <b>DIQQAT ESKALATSIYA!</b>\nLid #{lead_id} 15 daqiqadan beri qabul qilinmadi!",
                    reply_to=msg_id, parse_mode="html",
                )

    async def process_new_lead(
        self,
        chat_text: str,
        user_id: int,
        name: str,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        source: str = "Telegram DM",
    ) -> bool:
        """The 'Golden Path' for processing incoming leads."""
        logger.info(f"👸 [ORCHESTRATOR] Processing lead: {name} (Source: {source})")
        is_lead, lead_details = await self._qualify_incoming_lead(chat_text, name)
        if not is_lead:
            return False

        lead_id, is_repeat = await self._sync_with_amocrm(name, phone, user_id, username, source, lead_details)
        mgr_id, dist_text = await self._resolve_assigned_manager()
        await self._notify_team_and_escalate(
            name, username, user_id, phone, source, lead_details, lead_id, is_repeat, mgr_id, dist_text
        )
        return True
