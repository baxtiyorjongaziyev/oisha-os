"""Cashflow hisoboti — har kuni 19:00, shu oyning kirim/chiqim/sof oqimi."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.schedulers.moliya.helpers import (
    esc,
    fmt,
    read_name_map,
    read_table,
    select_name,
    send,
)

logger = logging.getLogger(__name__)

KATEGORIYA_JADVALLARI = ("Kategoriyalar", "Kategoriya", "Xarajat kategoriyalari")


def kategoriya_nomi(value: Any, nomlar: dict[str, str]) -> str:
    """Linked-record qiymatini o'qiladigan nomga aylantirish — xom rec ID chiqmaydi."""
    items = value if isinstance(value, list) else [value] if value else []
    out = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or nomlar.get(item.get("id", ""), "")
        else:
            s = str(item)
            name = nomlar.get(s, "" if s.startswith("rec") else s)
        out.append(name or "Nomsiz kategoriya")
    return ", ".join(out) or "Kategoriyasiz"


async def build_cashflow_report(now: datetime) -> str:
    records = await read_table("Tranzaksiyalar")
    nomlar = await read_name_map(*KATEGORIYA_JADVALLARI)
    oy = now.strftime("%Y-%m")

    kirim = chiqim = 0.0
    kirim_soni = chiqim_soni = 0
    kategoriyalar: dict[str, float] = {}
    kat_soni: dict[str, int] = {}

    for r in records:
        f = r.get("fields", {}) or {}

        if select_name(f.get("Holat")) == "Bekor qilingan":
            continue

        sana = f.get("Sana") or ""
        if not str(sana).startswith(oy):
            continue

        turi = select_name(f.get("Turi"))
        try:
            summa = float(f.get("Summa UZS") or 0)
        except (TypeError, ValueError):
            summa = 0.0

        if turi == "Kirim":
            kirim += summa
            kirim_soni += 1
        elif turi == "Chiqim":
            chiqim += summa
            chiqim_soni += 1
            kat = kategoriya_nomi(f.get("Kategoriya"), nomlar)
            kategoriyalar[kat] = kategoriyalar.get(kat, 0.0) + summa
            kat_soni[kat] = kat_soni.get(kat, 0) + 1

    sof = kirim - chiqim
    belgi = "🟢" if sof >= 0 else "🔴"

    lines = [
        f"📊 <b>Cashflow — {oy}</b>\n",
        f"Kirim:  <b>{fmt(kirim)}</b> so‘m  ({kirim_soni} ta)",
        f"Chiqim: <b>{fmt(chiqim)}</b> so‘m  ({chiqim_soni} ta)",
        f"{belgi} Sof oqim: <b>{fmt(sof)}</b> so‘m",
    ]

    if kategoriyalar:
        top = sorted(kategoriyalar.items(), key=lambda kv: kv[1], reverse=True)[:7]
        lines.append("\n<b>Eng katta xarajatlar:</b>")
        for kat, summa in top:
            ulush = (summa / chiqim * 100) if chiqim else 0
            lines.append(
                f"• {esc(kat)} — {fmt(summa)} ({ulush:.0f}%) · {kat_soni.get(kat, 0)} ta"
            )

    if not kirim_soni and not chiqim_soni:
        lines.append("\n<i>Bu oyda hali tranzaksiya yo‘q.</i>")

    return "\n".join(lines)


async def run_cashflow_report(now: datetime) -> bool:
    text = await build_cashflow_report(now)
    ok = await send(text, "HISOBCHI_CASHFLOW_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] Cashflow hisoboti yuborildi")
    return ok
