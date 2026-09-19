"""Durable multi-channel delivery checkpoints for Meta Lead Ads."""
from __future__ import annotations

import asyncio
import datetime
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "leadgen_delivery.db"
_ROUTING_LOCK = asyncio.Lock()


@contextmanager
def _connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS deliveries "
            "(leadgen_id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL)"
        )
        # Safe schema migrations for multi-channel tracking
        for col, col_def in (
            ("amocrm_ok", "INTEGER DEFAULT 1"),
            ("sheets_ok", "INTEGER DEFAULT 1"),
            ("telegram_ok", "INTEGER DEFAULT 1"),
            ("retries", "INTEGER DEFAULT 0"),
            ("last_error", "TEXT DEFAULT ''"),
            ("updated_at", "TEXT DEFAULT ''"),
        ):
            try:
                conn.execute(f"ALTER TABLE deliveries ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass
        yield conn


def get_crm_checkpoint(leadgen_id: str) -> int | None:
    """Return AmoCRM lead ID if already checkpointed."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT lead_id FROM deliveries WHERE leadgen_id = ?", (leadgen_id,)
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def save_crm_checkpoint(leadgen_id: str, lead_id: int) -> None:
    """Save AmoCRM lead checkpoint."""
    now = datetime.datetime.now().isoformat()
    with _connection() as conn:
        conn.execute(
            "INSERT INTO deliveries (leadgen_id, lead_id, amocrm_ok, updated_at) "
            "VALUES (?, ?, 1, ?) "
            "ON CONFLICT(leadgen_id) DO UPDATE SET "
            "lead_id = excluded.lead_id, amocrm_ok = 1, updated_at = excluded.updated_at",
            (str(leadgen_id), int(lead_id), now),
        )


def record_delivery_status(
    leadgen_id: str,
    lead_id: Optional[int],
    amocrm_ok: bool,
    sheets_ok: bool,
    telegram_ok: bool,
    error: str = "",
) -> None:
    """Record delivery outcome for all 3 channels: AmoCRM, Sheets, and Telegram."""
    now = datetime.datetime.now().isoformat()
    lid = int(lead_id) if lead_id is not None else None
    with _connection() as conn:
        conn.execute(
            "INSERT INTO deliveries (leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, last_error, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(leadgen_id) DO UPDATE SET "
            "lead_id = COALESCE(excluded.lead_id, deliveries.lead_id), "
            "amocrm_ok = excluded.amocrm_ok, "
            "sheets_ok = excluded.sheets_ok, "
            "telegram_ok = excluded.telegram_ok, "
            "last_error = excluded.last_error, "
            "updated_at = excluded.updated_at",
            (str(leadgen_id), lid, int(amocrm_ok), int(sheets_ok), int(telegram_ok), error, now),
        )


def mark_channel_delivered(leadgen_id: str, channel: str) -> None:
    """Mark a specific channel as successfully delivered."""
    now = datetime.datetime.now().isoformat()
    clean_id = str(leadgen_id)
    with _connection() as conn:
        if channel == "amocrm":
            conn.execute("UPDATE deliveries SET amocrm_ok = 1, updated_at = ? WHERE leadgen_id = ?", (now, clean_id))
        elif channel == "sheets":
            conn.execute("UPDATE deliveries SET sheets_ok = 1, updated_at = ? WHERE leadgen_id = ?", (now, clean_id))
        elif channel == "telegram":
            conn.execute("UPDATE deliveries SET telegram_ok = 1, updated_at = ? WHERE leadgen_id = ?", (now, clean_id))


def get_pending_deliveries(limit: int = 50) -> List[Dict[str, Any]]:
    """Return deliveries where any of AmoCRM, Sheets, or Telegram has not succeeded."""
    with _connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, retries, last_error, updated_at "
            "FROM deliveries "
            "WHERE (amocrm_ok = 0 OR sheets_ok = 0 OR telegram_ok = 0) "
            "AND retries < 10 "
            "ORDER BY rowid ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def increment_delivery_retry(leadgen_id: str, error: str = "") -> None:
    """Increment retry counter for a pending lead."""
    now = datetime.datetime.now().isoformat()
    with _connection() as conn:
        conn.execute(
            "UPDATE deliveries SET retries = retries + 1, last_error = ?, updated_at = ? "
            "WHERE leadgen_id = ?",
            (error, now, str(leadgen_id)),
        )


def get_delivery_summary(hours: int = 24) -> Dict[str, Any]:
    """Return delivery statistics for the given time window."""
    since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).isoformat()
    with _connection() as conn:
        row = conn.execute(
            "SELECT "
            "count(1) as total, "
            "sum(CASE WHEN amocrm_ok = 1 THEN 1 ELSE 0 END) as amo_count, "
            "sum(CASE WHEN sheets_ok = 1 THEN 1 ELSE 0 END) as sheets_count, "
            "sum(CASE WHEN telegram_ok = 1 THEN 1 ELSE 0 END) as tg_count, "
            "sum(CASE WHEN (amocrm_ok = 0 OR sheets_ok = 0 OR telegram_ok = 0) THEN 1 ELSE 0 END) as pending "
            "FROM deliveries WHERE updated_at >= ?",
            (since,),
        ).fetchone()

    total = row[0] or 0
    return {
        "total": total,
        "amocrm_ok": row[1] or 0,
        "sheets_ok": row[2] or 0,
        "telegram_ok": row[3] or 0,
        "pending": row[4] or 0,
        "hours": hours,
    }

