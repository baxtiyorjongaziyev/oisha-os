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
