"""CRM note approval flow — Telegram inline keyboard orqali tasdiqlash/tahrirlash."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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


def _h(text: Any) -> str:
    """HTML special char'larni escape qilish — Telegram HTML parse mode uchun."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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

    rubrik = analysis.get("rubrik_baholar") or {}
    r_salom = int(rubrik.get("salomlashish") or 0)
    r_ehti = int(rubrik.get("ehtiyojlar") or 0)
    r_qiy = int(rubrik.get("qiymat") or 0)
    r_etir = int(rubrik.get("etirozlar") or 0)
    r_yak = int(rubrik.get("yakunlash") or 0)
    r_mul = int(rubrik.get("muloqot_sifati") or 0)

    cat_icon = CATEGORY_EMOJI.get(category, "📌")
    mood_icon = MOOD_EMOJI.get(mood, "🤔")
    dur = f"{call_duration // 60}:{call_duration % 60:02d}" if call_duration else "—"

    def _score_bar(score: int) -> str:
        filled = round(max(0, min(100, score)) / 10)
        return "█" * filled + "░" * (10 - filled) + f" {score}/100"

    lines = [
        "📞 <b>Qo'ng'iroq tahlili tayyor</b>",
        "",
        f"👤 <b>Mijoz:</b> {_h(lead_name)}",
        f"📱 <b>Raqam:</b> <code>{_h(phone)}</code>",
        f"⏱ <b>Davomiylik:</b> {dur}",
        "",
        "━━━━━━ <b>SUHBAT TAHLILI</b> ━━━━━━",
        f"🎯 <b>Sifat bahosi:</b> {_score_bar(sifat)}",
        f"💎 <b>Lead bahosi:</b> {_score_bar(lead_b)}",
        f"🗣 <b>Nisbat:</b> Mijoz {client_pct}% | Sotuvchi {agent_pct}%",
        f"{cat_icon} <b>Toifa:</b> {_h(category)}   {mood_icon} <b>Kayfiyat:</b> {_h(mood)}",
        "",
        "━━━━━━ <b>JON BRANDING RUBRIK</b> ━━━━━━",
        f"1. Salomlashish:    {_score_bar(r_salom)}",
        f"2. Ehtiyojlar:      {_score_bar(r_ehti)}",
        f"3. Qiymat:          {_score_bar(r_qiy)}",
        f"4. E'tirozlar (×2): {_score_bar(r_etir)}",
        f"5. Yakunlash  (×2): {_score_bar(r_yak)}",
        f"6. Muloqot sifati:  {_score_bar(r_mul)}",
    ]

    if suhbat_oilasi:
        lines.append(f"💬 <b>Suhbat oilasi:</b> {_h(suhbat_oilasi)}")
    if suhbat_domeni:
        lines.append(f"🏢 <b>Suhbat domeni:</b> {_h(suhbat_domeni)}")
    if baholash:
        lines.append(f"📊 <b>Baholash rejimi:</b> {_h(baholash)}")
    if mosligi:
        lines.append(f"✅ <b>Biznes mosligi:</b> {_h(mosligi)}")
    if servis:
        lines.append(f"🎨 <b>Servis yo'nalishi:</b> {_h(servis)}")

    lines += [
        "",
        "━━━━━━ <b>MIJOZ MA'LUMOTI</b> ━━━━━━",
        f"👔 <b>Lavozimi:</b> {_h(lavozim)}",
        f"🏭 <b>Kompaniya:</b> {_h(kompaniya)}",
        f"🤝 <b>Qaror qabul qiluvchi:</b> {_h(qaror)}",
        f"📍 <b>Joylashuv:</b> {_h(joylashuv)}",
    ]

    if malumotlar:
        lines.append("")
        lines.append("<b>📋 Ma'lumotlar:</b>")
        for m in malumotlar[:5]:
            lines.append(f"• {_h(m)}")

    lines += [
        "",
        "━━━━━━ <b>XULOSA</b> ━━━━━━",
        f"📝 {_h(summary)}",
        "",
        f"➡️ <b>Keyingi qadam:</b> {_h(next_steps)}",
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


async def _prune_pending(max_age_seconds: int = 86400) -> None:
    """Remove _pending entries older than max_age_seconds (default 24 h).

    Stale entries are auto-posted to CRM before eviction — prevents permanent
    data loss when the owner never responds within 24 hours.
    """
    cutoff = datetime.now(timezone.utc)
    stale = [
        (k, v) for k, v in list(_pending.items())
        if (cutoff - datetime.fromisoformat(v["created_at"]).replace(tzinfo=timezone.utc)).total_seconds() > max_age_seconds
    ]
    for k, v in stale:
        try:
            await post_notes_to_amocrm(v["amocrm"], v["lead_id"], v["note_texts"])
            logger.info("[CRM_NOTE] 24h timeout: lead %s uchun izoh avtomatik qo'shildi", v["lead_id"])
        except Exception as e:
            logger.error("[CRM_NOTE] 24h timeout auto-post xatolik lead %s: %s", v["lead_id"], e)
        _pending.pop(k, None)
    # Also evict _pending_edit entries whose approval target is no longer in _pending
    stale_edits = [uid for uid, akey in _pending_edit.items() if akey not in _pending]
    for uid in stale_edits:
        _pending_edit.pop(uid, None)


async def register_pending(
    lead_id: int,
    call_id: str,
    note_texts: List[str],
    analysis: Dict[str, Any],
    amocrm_client: Any,
) -> None:
    await _prune_pending()
    key = _approval_key(lead_id, call_id)
    _pending[key] = {
        "lead_id": lead_id,
        "call_id": call_id,
        "note_texts": note_texts,
        "analysis": analysis,
        "amocrm": amocrm_client,
        "created_at": datetime.now(timezone.utc).isoformat(),
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


async def post_notes_to_amocrm(amocrm_client: Any, lead_id: int, note_texts: List[str]) -> bool:
    """Bir nechta noteni ketma-ket yuboradi."""
    ok = True
    for nt in note_texts:
        if nt and nt.strip():
            ok = await post_note_to_amocrm(amocrm_client, lead_id, nt) and ok
    return ok


async def handle_callback(callback_data: str, bot_or_event: Any, new_text: str = "") -> bool:
    """
    Callback handler — aiogram yoki Telethon callback event'dan chaqiriladi.
    callback_data: 'crm_approve:lead_id:call_id' yoki 'crm_edit:...'
    new_text: tahrirlash uchun yangi matn (bo'lsa)
    """
    if callback_data.startswith("crm_approve:"):
        pending = _pending.get(callback_data)
        if not pending:
            try:
                answer_fn = getattr(bot_or_event, "answer", None)
                if answer_fn:
                    await answer_fn("⚠️ So'rov topilmadi (bot qayta ishga tushgandirmi?).")
            except Exception:
                pass
            return False
        ok = await post_notes_to_amocrm(
            pending["amocrm"], pending["lead_id"], pending["note_texts"]
        )
        if ok:
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
            try:
                answer_fn = getattr(bot_or_event, "answer", None)
                if answer_fn:
                    await answer_fn("⚠️ So'rov topilmadi (bot qayta ishga tushgandirmi?).")
            except Exception:
                pass
            return False
        if new_text:
            # Faqat birinchi noteni almashtiradi; mijoz profili o'zgarmaydi
            pending["note_texts"] = [new_text] + (
                pending["note_texts"][1:] if len(pending["note_texts"]) > 1 else []
            )
            ok = await post_notes_to_amocrm(
                pending["amocrm"], pending["lead_id"], pending["note_texts"]
            )
            if ok:
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
                # ACK the button click first (answerCallbackQuery ≤200 chars)
                answer_fn = getattr(bot_or_event, "answer", None)
                if answer_fn:
                    try:
                        await answer_fn("✏️ Tahrirlashni boshlang")
                    except Exception:
                        pass
                # Send full prompt as a regular message (no size limit)
                respond_fn = getattr(bot_or_event, "respond", None)
                if respond_fn:
                    first_note = (pending["note_texts"] or [""])[0]
                    await respond_fn(
                        "✏️ Yangi izoh matnini yuboring.\n"
                        f"(Joriy tahlil matni):\n`{first_note[:300]}`"
                    )
            except Exception:
                pass
            return True

    return False


def pop_pending_edit(user_id: int) -> Optional[str]:
    """Return and remove the approve_key awaiting edited text from user_id, or None."""
    return _pending_edit.pop(user_id, None)


def push_pending_edit(user_id: int, approve_key: str) -> None:
    """Edit rejimini tiklash uchun — pop_pending_edit bilan simmetrik."""
    _pending_edit[user_id] = approve_key


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
        """Tahlil natijasini Telegram'ga yuboradi — tasdiqlash kutiladi."""
        if not self.bot:
            logger.warning("[CRM_NOTE] Bot client yo'q — avtomatik post qilinmoqda")
            return await post_notes_to_amocrm(self.amocrm, lead_id, note_texts)

        # format_approval_message imzosi o'zgarmaydi — birinchi noteni preview uchun uzatamiz
        first_note = (note_texts or [""])[0]
        msg_text = format_approval_message(analysis, lead_name, phone, call_duration, first_note)
        await register_pending(lead_id, call_id, note_texts, analysis, self.amocrm)

        try:
            buttons = build_inline_keyboard_telethon(lead_id, call_id)
            if hasattr(self.bot, "send_message"):
                await self.bot.send_message(self.owner_id, msg_text, buttons=buttons, parse_mode="html")
            elif hasattr(self.bot, "send"):
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
        """ENABLE_AUTO_REPLY=true bo'lsa tasdiqlashsiz to'g'ridan AMO ga yozadi."""
        return await post_notes_to_amocrm(self.amocrm, lead_id, note_texts)
