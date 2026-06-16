"""CRM note approval flow — Telegram inline keyboard orqali tasdiqlash/tahrirlash."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MOOD_EMOJI = {
    "Ijobiy": "😊",
    "Neytral": "😐",
    "Salbiy": "😟",
    "Noaniq": "🤔",
}

CATEGORY_EMOJI = {
    "Mijoz": "🤝",
    "Jamoa": "👥",
    "Shaxsiy": "👤",
    "Oila": "🏠",
    "Boshqa": "📌",
}

# Pending approvals: callback_data -> {lead_id, note_text, analysis, amocrm}
_pending: Dict[str, Dict[str, Any]] = {}


def _approval_key(lead_id: int, call_id: str) -> str:
    return f"crm_approve:{lead_id}:{call_id}"


def _edit_key(lead_id: int, call_id: str) -> str:
    return f"crm_edit:{lead_id}:{call_id}"


def format_approval_message(
    analysis: Dict[str, Any],
    lead_name: str,
    phone: str,
    call_duration: int = 0,
    note_text: str = "",
) -> str:
    category = analysis.get("category", "Boshqa")
    mood = analysis.get("client_mood", "Noaniq")
    summary = analysis.get("summary", "")
    next_steps = analysis.get("next_steps", "")
    client_pct = analysis.get("client_talk_pct", 0)
    agent_pct = analysis.get("agent_talk_pct", 0)

    cat_icon = CATEGORY_EMOJI.get(category, "📌")
    mood_icon = MOOD_EMOJI.get(mood, "🤔")
    dur = f"{call_duration // 60}:{call_duration % 60:02d}" if call_duration else "—"

    lines = [
        f"📞 *Qo'ng'iroq tahlili tayyor*",
        f"",
        f"👤 *Mijoz:* {lead_name}",
        f"📱 *Raqam:* `{phone}`",
        f"⏱ *Davomiylik:* {dur}",
        f"",
        f"{cat_icon} *Toifa:* {category}",
        f"{mood_icon} *Kayfiyat:* {mood}",
        f"🗣 *Nisbat:* Mijoz {client_pct}% | Sotuvchi {agent_pct}%",
        f"",
        f"📝 *Xulosa:*",
        f"{summary}",
        f"",
        f"➡️ *Keyingi qadam:*",
        f"{next_steps}",
        f"",
        f"✅ Tasdiqlang yoki ✏️ tahrirlang",
    ]
    return "\n".join(lines)


def build_inline_keyboard_aiogram(lead_id: int, call_id: str) -> list:
    """aiogram InlineKeyboardMarkup uchun button ro'yxati."""
    approve_cb = _approval_key(lead_id, call_id)
    edit_cb = _edit_key(lead_id, call_id)
    return [
        [
            {"text": "✅ Tasdiqlash", "callback_data": approve_cb},
            {"text": "✏️ Tahrirlash", "callback_data": edit_cb},
        ]
    ]


def build_inline_keyboard_telethon(lead_id: int, call_id: str):
    """Telethon Button uchun."""
    try:
        from telethon import Button
        approve_cb = _approval_key(lead_id, call_id)
        edit_cb = _edit_key(lead_id, call_id)
        return [Button.inline("✅ Tasdiqlash", data=approve_cb),
                Button.inline("✏️ Tahrirlash", data=edit_cb)]
    except ImportError:
        return None


def register_pending(
    lead_id: int,
    call_id: str,
    note_text: str,
    analysis: Dict[str, Any],
    amocrm_client: Any,
) -> None:
    key = _approval_key(lead_id, call_id)
    _pending[key] = {
        "lead_id": lead_id,
        "call_id": call_id,
        "note_text": note_text,
        "analysis": analysis,
        "amocrm": amocrm_client,
        "created_at": datetime.utcnow().isoformat(),
    }


async def post_note_to_amocrm(amocrm_client: Any, lead_id: int, note_text: str) -> bool:
    try:
        payload = [{"lead_id": lead_id, "note_type": "common", "params": {"text": note_text}}]
        result = await amocrm_client.create_notes(lead_id=lead_id, notes=payload)
        if result:
            logger.info("[CRM_NOTE] Lead %s ga izoh qo'shildi", lead_id)
            return True
        # Fallback: REST POST
        resp = await amocrm_client._request(
            "POST", "/api/v4/leads/notes",
            json=[{"entity_id": lead_id, "note_type": "common", "params": {"text": note_text}}]
        )
        return bool(resp)
    except Exception as e:
        logger.error("[CRM_NOTE] AMO POST xatolik: %s", e)
        return False


async def handle_callback(callback_data: str, bot_or_event: Any, new_text: str = "") -> bool:
    """
    Callback handler — aiogram yoki Telethon callback event'dan chaqiriladi.
    callback_data: 'crm_approve:lead_id:call_id' yoki 'crm_edit:...'
    new_text: tahrirlash uchun yangi matn (bo'lsa)
    """
    if callback_data.startswith("crm_approve:"):
        pending = _pending.get(callback_data)
        if not pending:
            return False
        ok = await post_note_to_amocrm(
            pending["amocrm"], pending["lead_id"], pending["note_text"]
        )
        _pending.pop(callback_data, None)
        try:
            reply_fn = getattr(bot_or_event, "answer", None) or getattr(bot_or_event, "respond", None)
            if reply_fn:
                msg = "✅ CRM ga izoh qo'shildi!" if ok else "❌ CRM ga yozishda xatolik"
                await reply_fn(msg)
        except Exception:
            pass
        return ok

    if callback_data.startswith("crm_edit:"):
        approve_key = callback_data.replace("crm_edit:", "crm_approve:", 1)
        pending = _pending.get(approve_key)
        if not pending:
            return False
        if new_text:
            pending["note_text"] = new_text
            ok = await post_note_to_amocrm(
                pending["amocrm"], pending["lead_id"], new_text
            )
            _pending.pop(approve_key, None)
            try:
                reply_fn = getattr(bot_or_event, "answer", None) or getattr(bot_or_event, "respond", None)
                if reply_fn:
                    msg = "✅ Tahrirlangan izoh CRM ga qo'shildi!" if ok else "❌ Xatolik"
                    await reply_fn(msg)
            except Exception:
                pass
            return ok
        else:
            try:
                reply_fn = getattr(bot_or_event, "answer", None) or getattr(bot_or_event, "respond", None)
                if reply_fn:
                    await reply_fn(
                        "✏️ Yangi izoh matnini yuboring.\n"
                        f"(Joriy matn):\n`{pending['note_text'][:300]}`"
                    )
            except Exception:
                pass
            return True

    return False


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
        note_text: str,
        call_duration: int = 0,
    ) -> bool:
        """Tahlil natijasini Telegram'ga yuboradi — tasdiqlash kutiladi."""
        if not self.bot:
            logger.warning("[CRM_NOTE] Bot client yo'q — avtomatik post qilinmoqda")
            return await post_note_to_amocrm(self.amocrm, lead_id, note_text)

        msg_text = format_approval_message(analysis, lead_name, phone, call_duration, note_text)
        register_pending(lead_id, call_id, note_text, analysis, self.amocrm)

        try:
            buttons = build_inline_keyboard_telethon(lead_id, call_id)
            if hasattr(self.bot, "send_message"):
                await self.bot.send_message(self.owner_id, msg_text, buttons=buttons, parse_mode="md")
            elif hasattr(self.bot, "send"):
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb_rows = build_inline_keyboard_aiogram(lead_id, call_id)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]) for b in row]
                    for row in kb_rows
                ])
                await self.bot.send_message(self.owner_id, msg_text, reply_markup=markup, parse_mode="Markdown")
            logger.info("[CRM_NOTE] Lead %s uchun approval yuborildi", lead_id)
            return True
        except Exception as e:
            logger.error("[CRM_NOTE] Telegram yuborishda xatolik: %s", e)
            return await post_note_to_amocrm(self.amocrm, lead_id, note_text)

    async def auto_post_without_approval(
        self, lead_id: int, note_text: str
    ) -> bool:
        """ENABLE_AUTO_REPLY=true bo'lsa tasdiqlashsiz to'g'ridan AMO ga yozadi."""
        return await post_note_to_amocrm(self.amocrm, lead_id, note_text)
