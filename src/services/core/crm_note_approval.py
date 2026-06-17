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
# Tracks users waiting to send edited note text: user_id -> approve_key
_pending_edit: Dict[int, str] = {}


def _safe_call_id(call_id: str, lead_id: int) -> str:
    """Telegram callback_data ≤64 bytes. Always truncate using the LONGEST
    prefix ('crm_approve') so both approval and edit keys share the same
    call_id slice — enabling the edit→approve key reconstruction in handle_callback.
    """
    longest_prefix = "crm_approve"
    max_id_len = 64 - len(longest_prefix) - len(str(lead_id)) - 2
    return call_id[:max_id_len]


def _approval_key(lead_id: int, call_id: str) -> str:
    return f"crm_approve:{lead_id}:{_safe_call_id(call_id, lead_id)}"


def _edit_key(lead_id: int, call_id: str) -> str:
    return f"crm_edit:{lead_id}:{_safe_call_id(call_id, lead_id)}"


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

    # MetaSell-like extended fields
    sifat = analysis.get("sifat_bahosi", 0)
    lead_b = analysis.get("lead_bahosi", 0)
    suhbat_oilasi = analysis.get("suhbat_oilasi", "")
    suhbat_domeni = analysis.get("suhbat_domeni", "")
    baholash = analysis.get("baholash_rejimi", "")
    mosligi = analysis.get("biznes_mosligi", "")
    servis = analysis.get("servis_yonalishi", "")
    lavozim = analysis.get("mijoz_lavozimi", "N/A")
    kompaniya = analysis.get("mijoz_kompaniya", "N/A")
    qaror = analysis.get("qaror_qabul_qiluvchi", "Noaniq")
    joylashuv = analysis.get("joylashuv", "N/A")
    malumotlar = analysis.get("mijoz_malumotlari", [])

    cat_icon = CATEGORY_EMOJI.get(category, "📌")
    mood_icon = MOOD_EMOJI.get(mood, "🤔")
    dur = f"{call_duration // 60}:{call_duration % 60:02d}" if call_duration else "—"

    def _score_bar(score: int) -> str:
        filled = round(score / 10)
        return "█" * filled + "░" * (10 - filled) + f" {score}/100"

    lines = [
        "📞 *Qo'ng'iroq tahlili tayyor*",
        "",
        f"👤 *Mijoz:* {lead_name}",
        f"📱 *Raqam:* `{phone}`",
        f"⏱ *Davomiylik:* {dur}",
        "",
        "━━━━━━ *SUHBAT TAHLILI* ━━━━━━",
        f"🎯 *Sifat bahosi:* {_score_bar(sifat)}",
        f"💎 *Lead bahosi:* {_score_bar(lead_b)}",
        f"🗣 *Nisbat:* Mijoz {client_pct}% | Sotuvchi {agent_pct}%",
        f"{cat_icon} *Toifa:* {category}   {mood_icon} *Kayfiyat:* {mood}",
    ]

    if suhbat_oilasi:
        lines.append(f"💬 *Suhbat oilasi:* {suhbat_oilasi}")
    if suhbat_domeni:
        lines.append(f"🏢 *Suhbat domeni:* {suhbat_domeni}")
    if baholash:
        lines.append(f"📊 *Baholash rejimi:* {baholash}")
    if mosligi:
        lines.append(f"✅ *Biznes mosligi:* {mosligi}")
    if servis:
        lines.append(f"🎨 *Servis yo'nalishi:* {servis}")

    lines += [
        "",
        "━━━━━━ *MIJOZ MA'LUMOTI* ━━━━━━",
        f"👔 *Lavozimi:* {lavozim}",
        f"🏭 *Kompaniya:* {kompaniya}",
        f"🤝 *Qaror qabul qiluvchi:* {qaror}",
        f"📍 *Joylashuv:* {joylashuv}",
    ]

    if malumotlar:
        lines.append("")
        lines.append("📋 *Ma'lumotlar:*")
        for m in malumotlar[:5]:
            lines.append(f"• {m}")

    lines += [
        "",
        "━━━━━━ *XULOSA* ━━━━━━",
        f"📝 {summary}",
        "",
        f"➡️ *Keyingi qadam:* {next_steps}",
        "",
        "✅ Tasdiqlang yoki ✏️ tahrirlang",
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
        import asyncio
        result = await asyncio.to_thread(amocrm_client.add_lead_note, lead_id, note_text)
        if result:
            logger.info("[CRM_NOTE] Lead %s ga izoh qo'shildi", lead_id)
            return True
        return False
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
                user_id = getattr(bot_or_event, "sender_id", None)
                if user_id:
                    _pending_edit[user_id] = approve_key
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


def pop_pending_edit(user_id: int) -> Optional[str]:
    """Return and remove the approve_key awaiting edited text from user_id, or None."""
    return _pending_edit.pop(user_id, None)


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
