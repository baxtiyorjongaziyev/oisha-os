"""CPL / xarajat anomaliyalari: kecha vs oldingi 7 kun o'rtachasi (kampaniya kesimida).

Ogohlantirish turlari:
  * cpl_spike   — kechagi CPL o'rtachadan `CPL_SPIKE_RATIO` marta yuqori
  * no_leads    — kecha sezilarli xarajat bor, lekin 0 lid
  * spend_stop  — oldin xarajat bo'lgan, kecha 0 (kampaniya to'xtagan / to'lov muammosi)
Har (sana, kampaniya, tur) uchun bitta marta yuboriladi.
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from typing import Any, Dict, List

from src.services.core.marketing import ad_spend_store

logger = logging.getLogger(__name__)

CPL_SPIKE_RATIO = 1.5
MIN_SPEND_FOR_ALERT = 50_000.0  # so'm — kichik xarajatdagi shovqinni o'tkazib yuboradi
BASELINE_DAYS = 7

_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS cpl_alerts_sent (
    date TEXT NOT NULL, campaign_id TEXT NOT NULL, kind TEXT NOT NULL,
    PRIMARY KEY (date, campaign_id, kind)
)
"""


def detect_anomalies(day: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`rows`: meta_ad_spend qatorlari (date, campaign_id, campaign_name, spend, meta_leads)."""
    by_campaign: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        c = by_campaign.setdefault(str(r["campaign_id"]), {"name": r.get("campaign_name") or "",
                                                           "today": None, "base": []})
        if r["date"] == day:
            c["today"] = r
        elif r["date"] < day:
            c["base"].append(r)

    alerts: List[Dict[str, Any]] = []
    for cid, c in by_campaign.items():
        base_spend = sum(float(b.get("spend") or 0) for b in c["base"])
        base_leads = sum(int(b.get("meta_leads") or 0) for b in c["base"])
        base_days = len([b for b in c["base"] if float(b.get("spend") or 0) > 0])
        today = c["today"] or {"spend": 0, "meta_leads": 0}
        spend, leads = float(today.get("spend") or 0), int(today.get("meta_leads") or 0)
        info = {"campaign_id": cid, "campaign_name": c["name"], "spend": spend, "leads": leads}

        if spend == 0 and base_days >= 3 and base_spend / base_days >= MIN_SPEND_FOR_ALERT:
            alerts.append({**info, "kind": "spend_stop", "baseline_spend": base_spend / base_days})
            continue
        if spend < MIN_SPEND_FOR_ALERT:
            continue
        base_cpl = base_spend / base_leads if base_leads else None
        if leads == 0:
            alerts.append({**info, "kind": "no_leads", "baseline_cpl": base_cpl})
        elif base_cpl and spend / leads >= base_cpl * CPL_SPIKE_RATIO:
            alerts.append({**info, "kind": "cpl_spike", "cpl": spend / leads, "baseline_cpl": base_cpl})
    return alerts


def _fmt(n: float) -> str:
    return f"{n:,.0f}".replace(",", " ")


def format_alerts(day: str, alerts: List[Dict[str, Any]]) -> str:
    lines = [f"⚠️ <b>Reklama ogohlantirishi</b> — {day}"]
    for a in alerts:
        name = a["campaign_name"] or a["campaign_id"]
        if a["kind"] == "cpl_spike":
            pct = (a["cpl"] / a["baseline_cpl"] - 1) * 100
            lines.append(f"📈 <b>{name}</b>: CPL {_fmt(a['cpl'])} so'm "
                         f"(7 kunlik o'rtacha {_fmt(a['baseline_cpl'])}, +{pct:.0f}%)")
        elif a["kind"] == "no_leads":
            lines.append(f"🕳 <b>{name}</b>: {_fmt(a['spend'])} so'm sarflandi, 0 lid")
        elif a["kind"] == "spend_stop":
            lines.append(f"⏸ <b>{name}</b>: kecha xarajat 0 (odatda ~{_fmt(a['baseline_spend'])}/kun) — "
                         f"to'lov yoki moderatsiyani tekshiring")
    return "\n".join(lines)


def _load_rows(day: str) -> List[Dict[str, Any]]:
    start = (dt.date.fromisoformat(day) - dt.timedelta(days=BASELINE_DAYS)).isoformat()
    with ad_spend_store._connection() as conn:
        rows = conn.execute(
            "SELECT date, campaign_id, campaign_name, spend, meta_leads FROM meta_ad_spend "
            "WHERE date BETWEEN ? AND ?", (start, day),
        ).fetchall()
    return [dict(r) for r in rows]


def _claim(conn: sqlite3.Connection, day: str, alert: Dict[str, Any]) -> bool:
    cur = conn.execute("INSERT OR IGNORE INTO cpl_alerts_sent VALUES (?, ?, ?)",
                       (day, alert["campaign_id"], alert["kind"]))
    return cur.rowcount == 1


def check_and_alert(day: str, send) -> int:
    """Kechagi kun uchun anomaliyalarni topib, yangilarini `send(text)` bilan yuboradi."""
    alerts = detect_anomalies(day, _load_rows(day))
    if not alerts:
        return 0
    with ad_spend_store._connection() as conn:
        conn.execute(_STATE_TABLE)
        fresh = [a for a in alerts if _claim(conn, day, a)]
        if fresh and not send(format_alerts(day, fresh)):
            conn.rollback()
            return 0
        conn.commit()
    if fresh:
        logger.info("[CPL MONITOR] %d ogohlantirish yuborildi (%s)", len(fresh), day)
    return len(fresh)
