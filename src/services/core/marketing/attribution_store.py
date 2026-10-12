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
# Keyin qo'shilgan ustunlar (eski DB'larga ALTER bilan qo'shiladi)
_EXTRA_COLUMNS = {
    "loss_reason_id": "INTEGER", "status_id": "INTEGER",
    "responsible_user_id": "INTEGER", "responsible_name": "TEXT",
    "lead_created_ts": "INTEGER", "first_touch_ts": "INTEGER",
}


@contextmanager
def _connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_TABLE)
        for stmt in _INDEXES:
            conn.execute(stmt)
        existing = {r[1] for r in conn.execute("PRAGMA table_info(lead_attribution)")}
        for col, typ in _EXTRA_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE lead_attribution ADD COLUMN {col} {typ}")  # nosec B608
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
    """AmoCRM yakuni noma'lum yozuvlar + rad etish sababi hali olinmagan yo'qotilganlar."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT leadgen_id, lead_id FROM lead_attribution
            WHERE lead_id IS NOT NULL
              AND (lead_won IS NULL OR (lead_won = 0 AND status_id IS NULL))
              AND created_at >= datetime('now', ?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"-{int(days)} days", int(limit)),
        ).fetchall()
    return [dict(row) for row in rows]


def update_revenue(
    leadgen_id: str, price: float, won: Optional[int], synced_at: str,
    status_id: Optional[int] = None, loss_reason_id: Optional[int] = None,
) -> None:
    with _connection() as conn:
        conn.execute(
            "UPDATE lead_attribution SET lead_price = ?, lead_won = ?, revenue_synced_at = ?, "
            "status_id = COALESCE(?, status_id), loss_reason_id = COALESCE(?, loss_reason_id) "
            "WHERE leadgen_id = ?",
            (price, won, synced_at, status_id, loss_reason_id, leadgen_id),
        )


def update_seller_info(
    leadgen_id: str, responsible_user_id: Optional[int], responsible_name: str,
    lead_created_ts: Optional[int], first_touch_ts: Optional[int],
) -> None:
    with _connection() as conn:
        conn.execute(
            "UPDATE lead_attribution SET responsible_user_id = COALESCE(?, responsible_user_id), "
            "responsible_name = COALESCE(NULLIF(?, ''), responsible_name), "
            "lead_created_ts = COALESCE(lead_created_ts, ?), "
            "first_touch_ts = COALESCE(first_touch_ts, ?) WHERE leadgen_id = ?",
            (responsible_user_id, responsible_name, lead_created_ts, first_touch_ts, leadgen_id),
        )


def has_first_touch(leadgen_id: str) -> bool:
    with _connection() as conn:
        row = conn.execute(
            "SELECT first_touch_ts FROM lead_attribution WHERE leadgen_id = ?", (leadgen_id,),
        ).fetchone()
    return bool(row and row["first_touch_ts"])


def seller_rows(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT responsible_user_id, responsible_name, lead_created_ts, first_touch_ts, lead_won
            FROM lead_attribution
            WHERE responsible_user_id IS NOT NULL
              AND date(created_at) >= date(?) AND date(created_at) <= date(?)
            """,
            (start_date, end_date),
        ).fetchall()
    return [dict(r) for r in rows]


def loss_breakdown(start_date: str, end_date: str) -> Dict[str, Any]:
    """Yo'qotilgan lidlarni toifa (reklama/sotuv) va sabab bo'yicha sanaydi."""
    from src.services.core.marketing.loss_reasons import classify, reason_name

    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT campaign_id, campaign_name, loss_reason_id FROM lead_attribution
            WHERE lead_won = 0 AND date(created_at) >= date(?) AND date(created_at) <= date(?)
            """,
            (start_date, end_date),
        ).fetchall()
    out: Dict[str, Any] = {"total": 0, "by_category": {}, "by_reason": {}, "by_campaign": {}}
    for row in rows:
        cat = classify(row["loss_reason_id"])
        name = reason_name(row["loss_reason_id"]) if row["loss_reason_id"] else "Sabab ko'rsatilmagan"
        out["total"] += 1
        out["by_category"][cat] = out["by_category"].get(cat, 0) + 1
        out["by_reason"][name] = out["by_reason"].get(name, 0) + 1
        camp = out["by_campaign"].setdefault(
            str(row["campaign_id"] or "unknown"),
            {"campaign_name": row["campaign_name"] or "", "reklama": 0, "sotuv": 0, "noma'lum": 0},
        )
        camp[cat] += 1
    return out


def count_recent_leads_for_campaign(campaign_id: str, days: int = 30) -> int:
    """Berilgan kampaniyada oxirgi `days` kunda tushgan leadlar soni."""
    if not campaign_id:
        return 0
    with _connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM lead_attribution
            WHERE campaign_id = ? AND created_at >= datetime('now', ?)
            """,
            (campaign_id, f"-{int(days)} days"),
        ).fetchone()
    return int(row["n"] or 0) if row else 0


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


def aggregate_by_ad(start_date: str, end_date: str, qualified_status_ids: set) -> Dict[str, Dict[str, Any]]:
    """Reklama (ad_id) bo'yicha CRM natijasi: lid, sifatli lid, sotuv, daromad."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT ad_id, status_id, lead_won, lead_price FROM lead_attribution
            WHERE ad_id != '' AND date(created_at) >= date(?) AND date(created_at) <= date(?)
            """,
            (start_date, end_date),
        ).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        b = out.setdefault(str(r["ad_id"]), {"crm_leads": 0, "qualified": 0, "won": 0, "revenue": 0.0})
        b["crm_leads"] += 1
        if r["lead_won"] == 1:
            b["won"] += 1
            b["qualified"] += 1
            b["revenue"] += float(r["lead_price"] or 0)
        elif r["status_id"] in qualified_status_ids:
            b["qualified"] += 1
    return out
