"""
CRM note approval orchestrator service.
"""
from __future__ import annotations

from typing import Any, Dict, List

import structlog
from src.services.core.crm.note_approval.formatters import (
    build_inline_keyboard_aiogram,
    build_inline_keyboard_telethon,
    format_approval_message,
)
from src.services.core.crm.note_approval.models import _approval_key
from src.services.core.crm.note_approval.state import (
    _pending,
    post_notes_to_amocrm,
    register_pending,
)

logger = structlog.get_logger()


class CRMNoteApprovalService:
    """Call analyzer bilan integratsiya — tahlildan so'ng Telegram approval yuboradi."""

    def __init__(self, amocrm_client: Any, owner_telegram_id: int, bot_client: Any = None):
        self.amocrm = amocrm_client
        self.owner_id = owner_telegram_id
        self.bot = bot_client

    async def send_for_approval(
        self,
        lead_id: int,
        lead_name: str,
        phone: str,
        call_id: str,
        analysis: Dict[str, Any],
        note_texts: List[str],
        call_duration: int = 0,
    ) -> bool:
        if not self.bot:
            logger.warning("[CRM_NOTE] Bot client yo'q — avtomatik post qilinmoqda")
            return await post_notes_to_amocrm(self.amocrm, lead_id, note_texts)

        first_note = (note_texts or [""])[0]
        msg_text = format_approval_message(analysis, lead_name, phone, call_duration, first_note)
        await register_pending(lead_id, call_id, note_texts, analysis, self.amocrm)

        try:
            buttons = build_inline_keyboard_telethon(lead_id, call_id)
            if hasattr(self.bot, "send_message"):
                await self.bot.send_message(self.owner_id, msg_text, buttons=buttons, parse_mode="html")
            elif hasattr(self.bot, "send"):
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                kb_rows = build_inline_keyboard_aiogram(lead_id, call_id)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]) for b in row]
                    for row in kb_rows
                ])
                await self.bot.send_message(self.owner_id, msg_text, reply_markup=markup, parse_mode="HTML")
            logger.info("[CRM_NOTE] Lead %s uchun approval yuborildi", lead_id)
            return True
        except Exception as e:
            logger.error("[CRM_NOTE] Telegram yuborishda xatolik: %s", e)
            _pending.pop(_approval_key(lead_id, call_id), None)
            return await post_notes_to_amocrm(self.amocrm, lead_id, note_texts)

    async def auto_post_without_approval(
        self, lead_id: int, note_texts: List[str]
    ) -> bool:
        return await post_notes_to_amocrm(self.amocrm, lead_id, note_texts)
