"""Balans hisoboti (har kuni 09:00) va kunlik balans eslatmasi (har kuni 20:00)."""

from __future__ import annotations

import logging

from src.schedulers.moliya.helpers import esc, fmt, read_table, select_name, send

logger = logging.getLogger(__name__)


async def build_balans_report() -> str:
    records = await read_table("Hisoblar")

    rows = []
    for r in records:
        f = r.get("fields", {}) or {}
        if f.get("Faol") is False:
            continue
        try:
            balans = float(f.get("Joriy balans (UZS)") or 0)
        except (TypeError, ValueError):
            balans = 0.0
        rows.append({
            "nom": f.get("Hisob nomi") or "Nomsiz",
            "turi": select_name(f.get("Turi")),
            "balans": balans,
        })

    if not rows:
        return "🏦 <b>Hisob qoldiqlari</b>\n\n<i>Hisoblar topilmadi.</i>"

    rows.sort(key=lambda x: x["balans"], reverse=True)
    jami = sum(x["balans"] for x in rows)

    emoji = {"Kassa": "💵", "Bank": "🏦", "Karta": "💳"}

    lines = ["🏦 <b>Hisob qoldiqlari</b>\n"]
    for x in rows:
        ico = emoji.get(x["turi"], "•")
        lines.append(f"{ico} {esc(x['nom'])} — <b>{fmt(x['balans'])}</b> so‘m")

    lines.append(f"\n<b>Jami: {fmt(jami)} so‘m</b>")

    if jami < 0:
        lines.append("\n⚠️ Umumiy qoldiq manfiy — tekshiring.")

    return "\n".join(lines)


async def run_balans_report() -> bool:
    text = await build_balans_report()
    ok = await send(text, "HISOBCHI_BALANCE_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Balans hisoboti yuborildi")
    return ok


async def run_balans_eslatmasi() -> bool:
    """Moliyachiga kunlik balansni kiritishni eslatadi (unutilmasligi uchun)."""
    text = (
        "🔔 <b>Eslatma:</b> @jonbranding_finansist — kunlik balansni kiritdingizmi?\n\n"
        "Har kuni unutmasdan yuborish kerak."
    )
    ok = await send(text, "HISOBCHI_BALANCE_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Kunlik balans eslatmasi yuborildi")
    return ok
