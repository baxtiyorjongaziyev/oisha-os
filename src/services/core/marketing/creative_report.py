"""Kreativlar (reklama/ad) solishtiruvi: xarajat, CPL, sifatli lid narxi, sotuv va ROAS.

Meta'dagi lid soni emas, CRM natijasi asosida — "qaysi video sotyapti" savoliga javob.
Haftada bir marta (Dushanba) marketing topic'iga yuboriladi.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Callable, Dict, List, Optional

from src.services.core.marketing import ad_spend_store, attribution_store
from src.services.core.marketing.meta_capi_triggers import _qualified_status_ids

logger = logging.getLogger(__name__)

MIN_SPEND = 50_000.0
MAX_ROWS = 10

_STATE_TABLE = "CREATE TABLE IF NOT EXISTS creative_reports_sent (week TEXT PRIMARY KEY)"


def build_rows(start: str, end: str) -> List[Dict[str, Any]]:
    spend = ad_spend_store.aggregate_ad_spend(start, end)
    crm = attribution_store.aggregate_by_ad(start, end, _qualified_status_ids())
    rows = []
    for ad_id in set(spend) | set(crm):
        s, c = spend.get(ad_id, {}), crm.get(ad_id, {})
        cost = float(s.get("spend") or 0)
        leads = int(c.get("crm_leads") or 0)
        qualified, won = int(c.get("qualified") or 0), int(c.get("won") or 0)
        revenue = float(c.get("revenue") or 0)
        rows.append({
            "ad_id": ad_id, "ad_name": s.get("ad_name") or ad_id, "spend": cost,
            "leads": leads, "qualified": qualified, "won": won, "revenue": revenue,
            "cpl": cost / leads if leads else None,
            "cpql": cost / qualified if qualified else None,
            "roas": revenue / cost if cost else None,
        })
    return sorted(rows, key=lambda r: -r["spend"])


def _money(v) -> str:
    return "—" if v is None else f"{v:,.0f}".replace(",", " ")


def format_report(start: str, end: str, rows: List[Dict[str, Any]]) -> str:
    rows = [r for r in rows if r["spend"] >= MIN_SPEND][:MAX_ROWS]
    if not rows:
        return ""
    lines = [f"🎬 <b>Kreativlar natijasi</b> ({start} — {end})", ""]
    for r in rows:
        roas = f"{r['roas']:.1f}x" if r["roas"] is not None else "—"
        lines.append(
            f"• <b>{r['ad_name']}</b>\n"
            f"   {_money(r['spend'])} so'm · {r['leads']} lid (CPL {_money(r['cpl'])}) · "
            f"{r['qualified']} sifatli ({_money(r['cpql'])}) · {r['won']} sotuv · ROAS {roas}"
        )
    best = min((r for r in rows if r["cpql"]), key=lambda r: r["cpql"], default=None)
    waste = [r for r in rows if r["leads"] >= 5 and r["qualified"] == 0]
    if best:
        lines += ["", f"✅ Eng arzon sifatli lid: <b>{best['ad_name']}</b> ({_money(best['cpql'])} so'm)"]
    if waste:
        lines.append("⚠️ Sifatli lid bermayapti: " + ", ".join(f"<b>{r['ad_name']}</b>" for r in waste))
    return "\n".join(lines)


def send_weekly_if_due(
    today: dt.date, send: Callable[[str], bool], send_pdf: Optional[Callable[[str], bool]] = None,
) -> bool:
    """Dushanba kuni o'tgan 7 kun hisobotini (va PDF'ni) bir marta yuboradi."""
    if today.weekday() != 0:
        return False
    week = today.isoformat()
    start = (today - dt.timedelta(days=7)).isoformat()
    end = (today - dt.timedelta(days=1)).isoformat()
    with ad_spend_store._connection() as conn:
        conn.execute(_STATE_TABLE)
        if conn.execute("SELECT 1 FROM creative_reports_sent WHERE week = ?", (week,)).fetchone():
            return False
        text = format_report(start, end, build_rows(start, end))
        if not text or not send(text):
            return False
        if send_pdf is not None:
            try:
                from src.services.core.marketing.pdf_report import weekly_pdf
                path = weekly_pdf(today, ad_spend_store._DB_PATH.parent / "reports")
                send_pdf(str(path))
            except Exception as exc:  # PDF yiqilsa ham matnli hisobot yuborilgan
                logger.warning("[CREATIVE REPORT] PDF yuborilmadi: %s", exc)
        conn.execute("INSERT INTO creative_reports_sent VALUES (?)", (week,))
        conn.commit()
    logger.info("[CREATIVE REPORT] Haftalik hisobot yuborildi (%s)", week)
    return True
