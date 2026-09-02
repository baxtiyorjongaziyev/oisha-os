"""
ActionParser — parses and executes tags ([CONTACT_INFO:...], [CALENDAR_EVENT:...], etc.) from AI replies.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import re
from typing import Any, Optional
from telegram import LabeledPrice

from src.services.core.tool_adapters import send_group_message_with_fallback

logger = logging.getLogger(__name__)


class ActionParser:
    """Parses and executes [TAG:...] actions from AI responses."""

    def __init__(
        self,
        db,
        gcontacts=None,
        gcalendar=None,
        invoicer=None,
        amocrm=None,
        config=None,
        lead_scraper=None,
        bot_app=None,
    ):
        self.db = db
        self.gcontacts = gcontacts
        self.gcalendar = gcalendar
        self.invoicer = invoicer
        self.amocrm = amocrm
        self.config = config
        self.lead_scraper = lead_scraper
        self.bot_app = bot_app

    def _process_lead_report(self, reply_text: str) -> tuple[str, Optional[str]]:
        lead_quality = None
        lead_match = re.search(r"\[LEAD_REPORT:\s*QUALITY\s*=\s*(.*?)\]", reply_text, re.IGNORECASE)
        if lead_match:
            lead_quality = str(lead_match.group(1)).strip().lower()
        if "Baxtiyorjon tez orada siz bilan bog'lanadi" in reply_text and not lead_quality:
            lead_quality = "sifatli"
        cleaned_text = re.sub(r"\[LEAD_REPORT:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()
        return cleaned_text, lead_quality

    def _process_contact_info(self, reply_text: str) -> str:
        contact_match = re.search(r"\[CONTACT_INFO:\s*(.*?)\]", reply_text, re.IGNORECASE)
        if contact_match and self.gcontacts:
            try:
                c_data = dict(part.split("=", 1) for part in str(contact_match.group(1) or "").split("|") if "=" in part)
                c_data = {k.strip(): v.strip() for k, v in c_data.items()}
                if c_data.get("name") or c_data.get("phone"):
                    self.gcontacts.create_contact(
                        first_name=c_data.get("name", "Noma'lum"),
                        phone=c_data.get("phone", ""),
                        note=c_data.get("note", "Telegram orqali avtomatik saqlandi"),
                    )
            except Exception as ce:
                logger.error(f"[ACTION_PARSER] Contact parsing error: {ce}")
        return re.sub(r"\[CONTACT_INFO:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

    def _process_save_info(self, reply_text: str, sender_id: int, sender_name: str, username: str) -> str:
        update_data = {}
        for match in re.finditer(r"\[SAVE_INFO:\s*(.*?)\]", reply_text, re.IGNORECASE):
            try:
                raw = str(match.group(1) or "")
                if "=" in raw:
                    k, v = raw.split("=", 1)
                    update_data[k.strip().lower()] = v.strip()
            except Exception as e:
                logger.error(f"[ACTION_PARSER] SAVE_INFO parsing error: {e}")

        if update_data and self.db:
            self.db.upsert_user(sender_id, sender_name, username=username, **update_data)
        return re.sub(r"\[SAVE_INFO:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

    async def _process_calendar_event(
        self, reply_text: str, sender_id: int, sender_name: str, username: str, context: Any
    ) -> str:
        cal_match = re.search(r"\[CALENDAR_EVENT:\s*(.*?)\]", reply_text, re.IGNORECASE)
        if not cal_match or not self.gcalendar:
            return re.sub(r"\[CALENDAR_EVENT:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

        try:
            cal_data = dict(part.split("=", 1) for part in str(cal_match.group(1) or "").split("|") if "=" in part)
            cal_data = {k.strip(): v.strip() for k, v in cal_data.items()}
            start_str = cal_data.get("start")
            if start_str and cal_data.get("summary"):
                end_str = cal_data.get("end") or start_str
                self.gcalendar.create_event(
                    summary=cal_data.get("summary"), start_time=start_str,
                    end_time=end_str, description=cal_data.get("description", ""),
                )
                if self.db:
                    self.db.update_meeting(sender_id, start_str)
                self._notify_meeting_group(sender_name, username, start_str, cal_data.get("summary", ""), context)
        except Exception as e:
            logger.error(f"[ACTION_PARSER] Calendar parsing error: {e}")
        return re.sub(r"\[CALENDAR_EVENT:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

    def _notify_meeting_group(self, sender_name: str, username: str, start_str: str, summary: str, context: Any) -> None:
        if not self.config or not getattr(self.config, "CRM_GROUP_ID", None) or not context:
            return
        crm_msg = (
            f"📅 <b>YANGI UCHRASHUV BELGILANDI!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Mijoz:</b> {sender_name} (@{username or 'yoq'})\n"
            f"🕒 <b>Vaqti:</b> {start_str}\n📝 <b>Mavzu:</b> {summary}\n"
        )
        asyncio.create_task(
            send_group_message_with_fallback(
                context.bot, chat_id=self.config.CRM_GROUP_ID, text=crm_msg,
                parse_mode="HTML", thread_id=getattr(self.config, "TOPIC_CRM_ID", None),
                allow_userbot_fallback=False,
            )
        )

    async def _process_sell_stars(self, reply_text: str, sender_id: int, context: Any) -> str:
        stars_match = re.search(r"\[SELL_STARS:\s*(.*?)\]", reply_text, re.IGNORECASE)
        if stars_match and context and getattr(context, "bot", None):
            try:
                s_data = dict(part.split("=", 1) for part in str(stars_match.group(1) or "").split("|") if "=" in part)
                s_data = {k.strip(): v.strip() for k, v in s_data.items()}
                amount = int(s_data.get("amount", "100"))
                title = s_data.get("title", "Jon Branding Xizmati")
                await context.bot.send_invoice(
                    chat_id=sender_id, title=title, description=title,
                    payload=f"stars_{sender_id}_{int(datetime.datetime.now().timestamp())}",
                    currency="XTR", prices=[LabeledPrice("Telegram Stars", amount)],
                )
            except Exception as se:
                logger.error(f"[ACTION_PARSER] Stars invoice error: {se}")
        return re.sub(r"\[SELL_STARS:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

    async def _process_invoice(self, reply_text: str, sender_id: int, context: Any) -> str:
        inv_match = re.search(r"\[INVOICE:\s*(.*?)\]", reply_text, re.IGNORECASE)
        if inv_match and self.invoicer:
            try:
                inv_data = dict(part.split("=", 1) for part in str(inv_match.group(1) or "").split("|") if "=" in part)
                inv_data = {k.strip(): v.strip() for k, v in inv_data.items()}
                amount = float(inv_data.get("amount", 0))
                if amount > 0:
                    link = await self.invoicer.create_invoice(
                        amount=amount, service=inv_data.get("service", "Branding"), user_id=sender_id,
                    )
                    if link and context and getattr(context, "bot", None):
                        await context.bot.send_message(
                            chat_id=sender_id, text=f"💳 To'lov havolasi: {link}",
                        )
            except Exception as ie:
                logger.error(f"[ACTION_PARSER] Invoicer error: {ie}")
        return re.sub(r"\[INVOICE:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

    async def _process_amocrm_push(
        self, reply_text: str, sender_id: int, sender_name: str, username: str, saved_phone: str, lead_quality: Optional[str]
    ) -> str:
        amo_match = re.search(r"\[PUSH_TO_AMOCRM:\s*(.*?)\]", reply_text, re.IGNORECASE)
        if (amo_match or lead_quality == "sifatli") and self.amocrm:
            try:
                lead_title = f"{sender_name} (@{username or 'no_user'})"
                phone = saved_phone
                if amo_match:
                    p_data = dict(part.split("=", 1) for part in str(amo_match.group(1) or "").split("|") if "=" in part)
                    p_data = {k.strip(): v.strip() for k, v in p_data.items()}
                    lead_title = p_data.get("title", lead_title)
                    phone = p_data.get("phone", phone)
                await self.amocrm.create_lead(
                    name=lead_title, phone=phone, user_id=sender_id,
                    notes=f"AI Agent orqali avtomatik yuborildi. Quality: {lead_quality}",
                )
            except Exception as ae:
                logger.error(f"[ACTION_PARSER] AmoCRM push error: {ae}")
        return re.sub(r"\[PUSH_TO_AMOCRM:.*?\]", "", reply_text, flags=re.IGNORECASE).strip()

    async def parse_and_execute(
        self,
        reply_text: str,
        sender_id: int,
        sender_name: str = "",
        username: str = "",
        saved_phone: str = "",
        context=None,
        is_business: bool = False,
        msg_business_connection_id: Optional[str] = None,
    ) -> str:
        """Parses all tags and executes their specific side-effects. Returns cleaned text."""
        reply_text, lead_quality = self._process_lead_report(reply_text)
        reply_text = self._process_contact_info(reply_text)
        reply_text = self._process_save_info(reply_text, sender_id, sender_name, username)
        reply_text = await self._process_calendar_event(reply_text, sender_id, sender_name, username, context)
        reply_text = await self._process_sell_stars(reply_text, sender_id, context)
        reply_text = await self._process_invoice(reply_text, sender_id, context)
        reply_text = await self._process_amocrm_push(reply_text, sender_id, sender_name, username, saved_phone, lead_quality)
        return reply_text.strip()
