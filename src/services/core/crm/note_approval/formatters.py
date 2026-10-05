"""
Message and keyboard formatters for CRM note approval.
"""
from __future__ import annotations

from typing import Any, Dict
from src.services.core.crm.note_approval.models import (
    CATEGORY_EMOJI,
    MOOD_EMOJI,
    _approval_key,
    _edit_key,
    _h,
)


_RUBRIC_ROWS = (
    ("1. Salomlashish:    ", "salomlashish"),
    ("2. Ehtiyojlar:      ", "ehtiyojlar"),
    ("3. Qiymat:          ", "qiymat"),
    ("4. E'tirozlar (×2): ", "etirozlar"),
    ("5. Yakunlash  (×2): ", "yakunlash"),
    ("6. Muloqot sifati:  ", "muloqot_sifati"),
)

_CONVERSATION_FIELDS = (
    ("suhbat_oilasi", "💬 <b>Suhbat oilasi:</b> "),
    ("suhbat_domeni", "🏢 <b>Suhbat domeni:</b> "),
    ("baholash_rejimi", "📊 <b>Baholash rejimi:</b> "),
    ("biznes_mosligi", "✅ <b>Biznes mosligi:</b> "),
    ("servis_yonalishi", "🎨 <b>Servis yo'nalishi:</b> "),
)


def _score_bar(score: int) -> str:
    filled = round(max(0, min(100, score)) / 10)
    return "█" * filled + "░" * (10 - filled) + f" {score}/100"


def _analysis_lines(analysis: Dict[str, Any], lead_name: str, phone: str, call_duration: int) -> list:
    category = analysis.get("category", "Boshqa")
    mood = analysis.get("client_mood", "Noaniq")
    cat_icon = CATEGORY_EMOJI.get(category, "📌")
    mood_icon = MOOD_EMOJI.get(mood, "🤔")
    dur = f"{call_duration // 60}:{call_duration % 60:02d}" if call_duration else "—"
    rubrik = analysis.get("rubrik_baholar") or {}

    lines = [
        "📞 <b>Qo'ng'iroq tahlili tayyor</b>",
        "",
        f"👤 <b>Mijoz:</b> {_h(lead_name)}",
        f"📱 <b>Raqam:</b> <code>{_h(phone)}</code>",
        f"⏱ <b>Davomiylik:</b> {dur}",
        "",
        "━━━━━━ <b>SUHBAT TAHLILI</b> ━━━━━━",
        f"🎯 <b>Sifat bahosi:</b> {_score_bar(analysis.get('sifat_bahosi', 0))}",
        f"💎 <b>Lead bahosi:</b> {_score_bar(analysis.get('lead_bahosi', 0))}",
        f"🗣 <b>Nisbat:</b> Mijoz {analysis.get('client_talk_pct', 0)}% | "
        f"Sotuvchi {analysis.get('agent_talk_pct', 0)}%",
        f"{cat_icon} <b>Toifa:</b> {_h(category)}   {mood_icon} <b>Kayfiyat:</b> {_h(mood)}",
        "",
        "━━━━━━ <b>JON BRANDING RUBRIK</b> ━━━━━━",
    ]
    lines += [f"{label}{_score_bar(int(rubrik.get(key) or 0))}" for label, key in _RUBRIC_ROWS]
    for key, label in _CONVERSATION_FIELDS:
        value = analysis.get(key, "")
        if value:
            lines.append(f"{label}{_h(value)}")
    return lines


def _client_lines(analysis: Dict[str, Any]) -> list:
    lines = [
        "",
        "━━━━━━ <b>MIJOZ MA'LUMOTI</b> ━━━━━━",
        f"👔 <b>Lavozimi:</b> {_h(analysis.get('mijoz_lavozimi', 'N/A'))}",
        f"🏭 <b>Kompaniya:</b> {_h(analysis.get('mijoz_kompaniya', 'N/A'))}",
        f"🤝 <b>Qaror qabul qiluvchi:</b> {_h(analysis.get('qaror_qabul_qiluvchi', 'Noaniq'))}",
        f"📍 <b>Joylashuv:</b> {_h(analysis.get('joylashuv', 'N/A'))}",
    ]
    malumotlar = analysis.get("mijoz_malumotlari", [])
    if malumotlar:
        lines.append("")
        lines.append("<b>📋 Ma'lumotlar:</b>")
        for m in malumotlar[:5]:
            lines.append(f"• {_h(m)}")
    return lines


def format_approval_message(
    analysis: Dict[str, Any],
    lead_name: str,
    phone: str,
    call_duration: int = 0,
    note_text: str = "",
) -> str:
    lines = _analysis_lines(analysis, lead_name, phone, call_duration)
    lines += _client_lines(analysis)
    lines += [
        "",
        "━━━━━━ <b>XULOSA</b> ━━━━━━",
        f"📝 {_h(analysis.get('summary', ''))}",
        "",
        f"➡️ <b>Keyingi qadam:</b> {_h(analysis.get('next_steps', ''))}",
        "",
        "✅ Tasdiqlang yoki ✏️ tahrirlang",
    ]
    return "\n".join(lines)


def build_inline_keyboard_aiogram(lead_id: int, call_id: str) -> list:
    approve_cb = _approval_key(lead_id, call_id)
    edit_cb = _edit_key(lead_id, call_id)
    return [
        [
            {"text": "✅ Tasdiqlash", "callback_data": approve_cb},
            {"text": "✏️ Tahrirlash", "callback_data": edit_cb},
        ]
    ]


def build_inline_keyboard_telethon(lead_id: int, call_id: str):
    try:
        from telethon import Button
        approve_cb = _approval_key(lead_id, call_id)
        edit_cb = _edit_key(lead_id, call_id)
        return [Button.inline("✅ Tasdiqlash", data=approve_cb),
                Button.inline("✏️ Tahrirlash", data=edit_cb)]
    except ImportError:
        return None
