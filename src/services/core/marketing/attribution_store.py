"""Local durable storage: Meta lead -> campaign -> AmoCRM natija bog'lanishi.

`leadgen_delivery.py` faqat `leadgen_id -> lead_id` saqlaydi (Telegram qayta
yuborishni oldini olish uchun). Marketing attribution uchun yana campaign_id
kerak — shuning uchun alohida jadval, lekin bir xil naqsh (mahalliy SQLite,
Turso emas — bu hisobot ma'lumoti, tranzaktsion CRM ma'lumoti emas).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "meta_ad_attribution.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS lead_attribution (
    leadgen_id TEXT PRIMARY KEY,
    lead_id INTEGER,
    campaign_id TEXT,
    campaign_name TEXT,
    ad_id TEXT,
    form_id TEXT,
    created_at TEXT,
    lead_price REAL DEFAULT 0,
    lead_won INTEGER,
    revenue_synced_at TEXT
)
"""
_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_attr_campaign ON lead_attribution(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_attr_created_at ON lead_attribution(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_attr_lead_id ON lead_attribution(lead_id)",
)


@contextmanager
def _connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_TABLE)
        for stmt in _INDEXES:
            conn.execute(stmt)
        yield conn


def save_attribution(
    leadgen_id: str,
    lead_id: Optional[int],
    campaign_id: str,
    campaign_name: str,
    ad_id: str,
    form_id: str,
    created_at: str,
) -> None:
    """Lead yaratilgan payt kampaniya izini yozib qo'yadi (idempotent)."""
    leadgen_id = str(leadgen_id).strip()
    if not leadgen_id:
        return
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO lead_attribution
                (leadgen_id, lead_id, campaign_id, campaign_name, ad_id, form_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(leadgen_id) DO UPDATE SET
                lead_id=excluded.lead_id,
                campaign_id=excluded.campaign_id,
                campaign_name=excluded.campaign_name,
                ad_id=excluded.ad_id,
                form_id=excluded.form_id
            """,
            (
                leadgen_id,
                int(lead_id) if lead_id else None,
                str(campaign_id or ""),
                str(campaign_name or ""),
                str(ad_id or ""),
                str(form_id or ""),
                created_at,
            ),
        )


def pending_revenue_sync(days: int = 90, limit: int = 200) -> List[Dict[str, Any]]:
    """AmoCRM yakuni hali noma'lum (lead_won IS NULL) yozuvlar."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT leadgen_id, lead_id FROM lead_attribution
            WHERE lead_id IS NOT NULL
              AND lead_won IS NULL
              AND created_at >= datetime('now', ?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"-{int(days)} days", int(limit)),
        ).fetchall()
    return [dict(row) for row in rows]


def update_revenue(leadgen_id: str, price: float, won: Optional[int], synced_at: str) -> None:
    with _connection() as conn:
        conn.execute(
            "UPDATE lead_attribution SET lead_price = ?, lead_won = ?, revenue_synced_at = ? "
            "WHERE leadgen_id = ?",
            (price, won, synced_at, leadgen_id),
        )


def aggregate_by_campaign(start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
    """`created_at` sanasi oralig'idagi leadlarni campaign_id bo'yicha yig'adi.

    Qaytaradi: {campaign_id: {campaign_name, leads, won, lost, open, revenue_won}}
    """
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT campaign_id, campaign_name, lead_won, lead_price
            FROM lead_attribution
            WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
            """,
            (start_date, end_date),
        ).fetchall()

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cid = str(row["campaign_id"] or "unknown")
        bucket = out.setdefault(
            cid,
            {
                "campaign_id": cid,
                "campaign_name": row["campaign_name"] or "",
                "leads": 0,
                "won": 0,
                "lost": 0,
                "open": 0,
                "revenue_won": 0.0,
            },
        )
        bucket["leads"] += 1
        if not bucket["campaign_name"] and row["campaign_name"]:
            bucket["campaign_name"] = row["campaign_name"]
        won = row["lead_won"]
        if won == 1:
            bucket["won"] += 1
            bucket["revenue_won"] += float(row["lead_price"] or 0)
        elif won == 0:
            bucket["lost"] += 1
        else:
            bucket["open"] += 1
    return out
