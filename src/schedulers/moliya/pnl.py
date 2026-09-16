"""P&L (foyda/zarar) hisoboti — har oyning 1-sanasi 09:00, o'tgan oy uchun."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.schedulers.moliya.helpers import UZBEK_MONTHS, fmt, read_table, send

logger = logging.getLogger(__name__)


def _prev_month_code(now: datetime) -> str:
    """2026-09-01 -> '2026-08' (o'tgan oyning kodi)."""
    first_of_this_month = now.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_of_prev_month.strftime("%Y-%m")


async def build_pnl_report(now: datetime) -> str:
    records = await read_table("Oylik P&L")
    oy_kodi = _prev_month_code(now)

    record = None
    for r in records:
        f = r.get("fields", {}) or {}
        if str(f.get("Oy nomi") or "")[:7] == oy_kodi:
            record = f
            break

    oy_nomi = UZBEK_MONTHS.get(oy_kodi[5:7], oy_kodi)
    if not record:
        return f"📈 <b>P&L — {oy_nomi}</b>\n\n<i>Bu oy uchun hali P&L yozuvi yo'q.</i>"

    kirim = record.get("Jami Kirim (UZS)") or 0
    chiqim = record.get("Jami Chiqim (UZS)") or 0
    soliqqacha = record.get("Soliqqacha foyda (UZS)") or 0
    soliq = record.get("Soliq xarajati (UZS)") or 0
    sof_foyda = record.get("Soliqdan keyingi sof foyda (UZS)") or 0
    dividend = record.get("Taqsimlangan dividend (UZS)") or 0
    taqsimlanmagan = record.get("Taqsimlanmagan foyda (UZS)") or 0
    marja = record.get("Sof foyda marjasi (%)")

    belgi = "🟢" if float(sof_foyda or 0) >= 0 else "🔴"

    lines = [
        f"📈 <b>P&L — {oy_nomi}</b>\n",
        f"Kirim:  <b>{fmt(kirim)}</b> so'm",
        f"Chiqim: <b>{fmt(chiqim)}</b> so'm",
        f"Soliqqacha foyda: <b>{fmt(soliqqacha)}</b> so'm",
        f"Soliq: <b>{fmt(soliq)}</b> so'm",
        f"{belgi} Sof foyda: <b>{fmt(sof_foyda)}</b> so'm",
    ]
    if marja is not None:
        try:
            lines.append(f"Sof foyda marjasi: <b>{float(marja) * 100:.1f}%</b>")
        except (TypeError, ValueError):
            pass
    lines.append(f"\nTaqsimlangan dividend: {fmt(dividend)} so'm")
    lines.append(f"Taqsimlanmagan foyda: {fmt(taqsimlanmagan)} so'm")

    return "\n".join(lines)


async def run_pnl_report(now: datetime) -> bool:
    text = await build_pnl_report(now)
    ok = await send(text, "HISOBCHI_PNL_TOPIC_ID")
    if ok:
        logger.info("[MOLIYA] P&L hisoboti yuborildi")
    return ok
