"""Qarzdorlik hisoboti — har dushanba 09:00, to'lovi tugallanmagan loyihalar."""

from __future__ import annotations

import logging

from src.schedulers.moliya.helpers import MAX_ROWS, esc, fmt, link_names, read_table, send

logger = logging.getLogger(__name__)


async def build_qarzdorlik_report() -> str:
    records = await read_table("Loyihalar")

    rows = []
    for r in records:
        f = r.get("fields", {}) or {}
        qoldiq = f.get("Qoldiq to‘lov uzs") or f.get("Qoldiq to'lov uzs") or 0
        try:
            qoldiq = float(qoldiq)
        except (TypeError, ValueError):
            qoldiq = 0
        if qoldiq <= 0:
            continue
        rows.append({
            "nom": f.get("Loyihani nomi?") or "Nomsiz",
            "mijoz": link_names(f.get("Mijoz nomi")),
            "narx": f.get("Jami loyiha narxi (UZS)") or 0,
            "tolangan": f.get("Jami to'langan (UZS)") or f.get("Jami to‘langan (UZS)") or 0,
            "qoldiq": qoldiq,
        })

    rows.sort(key=lambda x: x["qoldiq"], reverse=True)

    if not rows:
        return "💰 <b>Qarzdorlik</b>\n\nQarzdorlik yo‘q — barcha loyihalar to‘liq to‘langan ✅"

    jami = sum(x["qoldiq"] for x in rows)

    lines = [f"💰 <b>Qarzdorlik</b> — {len(rows)} ta loyiha\n"]
    for i, x in enumerate(rows[:MAX_ROWS], 1):
        lines.append(f"{i}. <b>{esc(x['nom'])}</b>")
        if x["mijoz"]:
            lines.append(f"    {esc(x['mijoz'])}")
        lines.append(
            f"    {fmt(x['tolangan'])} / {fmt(x['narx'])} — "
            f"qoldiq <b>{fmt(x['qoldiq'])}</b> so‘m"
        )

    if len(rows) > MAX_ROWS:
        qolgan = len(rows) - MAX_ROWS
        lines.append(f"\n<i>… yana {qolgan} ta loyiha</i>")

    lines.append(f"\n<b>Jami qarzdorlik: {fmt(jami)} so‘m</b>")
    return "\n".join(lines)


async def run_qarzdorlik_report() -> bool:
    text = await build_qarzdorlik_report()
    ok = await send(text, "HISOBCHI_QARZDORLIK_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Qarzdorlik hisoboti yuborildi")
    return ok
