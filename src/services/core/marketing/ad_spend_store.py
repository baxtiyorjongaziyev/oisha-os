"""Meta Ads kunlik xarajatining mahalliy keshi (kampaniya kesimida)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List

_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "meta_ad_spend.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS meta_ad_spend (
    date TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    campaign_name TEXT,
    spend REAL DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    meta_leads INTEGER DEFAULT 0,
    synced_at TEXT,
    PRIMARY KEY (date, campaign_id)
)
"""


_CREATE_AD_TABLE = """
CREATE TABLE IF NOT EXISTS meta_ad_spend_by_ad (
    date TEXT NOT NULL,
    ad_id TEXT NOT NULL,
    ad_name TEXT,
    campaign_id TEXT,
    campaign_name TEXT,
    spend REAL DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    meta_leads INTEGER DEFAULT 0,
    synced_at TEXT,
    PRIMARY KEY (date, ad_id)
)
"""


@contextmanager
def _connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_TABLE)
        conn.execute(_CREATE_AD_TABLE)
        yield conn


def upsert_daily_spend(rows: Iterable[Dict[str, Any]], synced_at: str) -> int:
    """Meta Insights qatorlarini (date, campaign_id) bo'yicha yozadi/yangilaydi."""
    written = 0
    with _connection() as conn:
        for row in rows:
            date = str(row.get("date") or "").strip()
            campaign_id = str(row.get("campaign_id") or "").strip()
            if not date or not campaign_id:
                continue
            conn.execute(
                """
                INSERT INTO meta_ad_spend
                    (date, campaign_id, campaign_name, spend, impressions, clicks, meta_leads, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, campaign_id) DO UPDATE SET
                    campaign_name=excluded.campaign_name,
                    spend=excluded.spend,
                    impressions=excluded.impressions,
                    clicks=excluded.clicks,
                    meta_leads=excluded.meta_leads,
                    synced_at=excluded.synced_at
                """,
                (
                    date,
                    campaign_id,
                    str(row.get("campaign_name") or ""),
                    float(row.get("spend") or 0),
                    int(row.get("impressions") or 0),
                    int(row.get("clicks") or 0),
                    int(row.get("meta_leads") or 0),
                    synced_at,
                ),
            )
            written += 1
        conn.commit()
    return written


def aggregate_spend(start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
    """`date` oralig'idagi xarajatni campaign_id bo'yicha yig'adi."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT campaign_id, campaign_name, SUM(spend) AS spend,
                   SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                   SUM(meta_leads) AS meta_leads
            FROM meta_ad_spend
            WHERE date >= ? AND date <= ?
            GROUP BY campaign_id
            """,
            (start_date, end_date),
        ).fetchall()

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cid = str(row["campaign_id"])
        out[cid] = {
            "campaign_id": cid,
            "campaign_name": row["campaign_name"] or "",
            "spend": float(row["spend"] or 0),
            "impressions": int(row["impressions"] or 0),
            "clicks": int(row["clicks"] or 0),
            "meta_leads": int(row["meta_leads"] or 0),
        }
    return out


def total_spend(start_date: str, end_date: str) -> float:
    with _connection() as conn:
        row = conn.execute(
            "SELECT SUM(spend) AS spend FROM meta_ad_spend WHERE date >= ? AND date <= ?",
            (start_date, end_date),
        ).fetchone()
    return float(row["spend"] or 0) if row else 0.0


def upsert_daily_ad_spend(rows: Iterable[Dict[str, Any]], synced_at: str) -> int:
    """Reklama (ad) kesimidagi kunlik qatorlarni yozadi — kreativlarni solishtirish uchun."""
    written = 0
    with _connection() as conn:
        for row in rows:
            date = str(row.get("date") or "").strip()
            ad_id = str(row.get("ad_id") or "").strip()
            if not date or not ad_id:
                continue
            conn.execute(
                """
                INSERT INTO meta_ad_spend_by_ad
                    (date, ad_id, ad_name, campaign_id, campaign_name, spend, impressions, clicks,
                     meta_leads, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, ad_id) DO UPDATE SET
                    ad_name=excluded.ad_name, campaign_id=excluded.campaign_id,
                    campaign_name=excluded.campaign_name, spend=excluded.spend,
                    impressions=excluded.impressions, clicks=excluded.clicks,
                    meta_leads=excluded.meta_leads, synced_at=excluded.synced_at
                """,
                (
                    date, ad_id, str(row.get("ad_name") or ""), str(row.get("campaign_id") or ""),
                    str(row.get("campaign_name") or ""), float(row.get("spend") or 0),
                    int(row.get("impressions") or 0), int(row.get("clicks") or 0),
                    int(row.get("meta_leads") or 0), synced_at,
                ),
            )
            written += 1
        conn.commit()
    return written


def aggregate_ad_spend(start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT ad_id, MAX(ad_name) AS ad_name, MAX(campaign_name) AS campaign_name,
                   SUM(spend) AS spend, SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                   SUM(meta_leads) AS meta_leads
            FROM meta_ad_spend_by_ad WHERE date >= ? AND date <= ? GROUP BY ad_id
            """,
            (start_date, end_date),
        ).fetchall()
    return {str(r["ad_id"]): dict(r) for r in rows}
