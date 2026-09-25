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
        conn.execute(
            "CREATE TABLE IF NOT EXISTS leadgen_routing_state "
            "(key TEXT PRIMARY KEY, last_destination TEXT, count INTEGER DEFAULT 0, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS leadgen_claims "
            "(leadgen_id TEXT PRIMARY KEY, claimed_at TEXT, pid INTEGER)"
        )
        # Safe schema migrations for multi-channel tracking
        for col, col_def in (
            ("amocrm_ok", "INTEGER DEFAULT 1"),
            ("sheets_ok", "INTEGER DEFAULT 0"),
            ("telegram_ok", "INTEGER DEFAULT 0"),
            ("destination", "TEXT DEFAULT ''"),
            ("retries", "INTEGER DEFAULT 0"),
            ("last_error", "TEXT DEFAULT ''"),
            ("updated_at", "TEXT DEFAULT ''"),
        ):
            try:
                conn.execute(f"ALTER TABLE deliveries ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass
        yield conn


def record_lead_destination(destination: str) -> None:
    """Record last chosen destination in routing state table."""
    dest = (destination or "").strip().lower()
    if dest not in ("utc", "inhouse"):
        return
    now = datetime.datetime.now().isoformat()
    with _connection() as conn:
        conn.execute(
            "INSERT INTO leadgen_routing_state (key, last_destination, count, updated_at) "
            "VALUES ('split_destination', ?, 1, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "last_destination = excluded.last_destination, "
            "count = leadgen_routing_state.count + 1, "
            "updated_at = excluded.updated_at",
            (dest, now),
        )


def get_lead_destination(leadgen_id: str) -> Optional[str]:
    """Return assigned destination ('utc' or 'inhouse') for a specific lead if already set."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT destination FROM deliveries WHERE leadgen_id = ?", (str(leadgen_id),)
        ).fetchone()
    if row and row[0] in ("utc", "inhouse"):
        return str(row[0])
    return None


def get_next_lead_destination() -> str:
    """Return 'utc' or 'inhouse' alternating 50/50 based on the last recorded destination."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT last_destination FROM leadgen_routing_state WHERE key = 'split_destination'"
        ).fetchone()
        if not row or not row[0]:
            d_row = conn.execute(
                "SELECT destination FROM deliveries "
                "WHERE destination IN ('utc', 'inhouse') "
                "ORDER BY updated_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            if not d_row or not d_row[0]:
                return "utc"
            row = d_row
    last_dest = str(row[0]).strip().lower()
    return "inhouse" if last_dest == "utc" else "utc"


def get_crm_checkpoint(leadgen_id: str) -> int | None:
    """Return AmoCRM lead ID if already checkpointed."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT lead_id FROM deliveries WHERE leadgen_id = ?", (leadgen_id,)
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def save_crm_checkpoint(
    leadgen_id: str, lead_id: int, destination: str = "", advance_rotation: bool = True,
) -> None:
    """Save AmoCRM lead checkpoint and destination.

    advance_rotation=False: lead joined an existing deal, so the 50/50 split must not move.
    """
    if destination and advance_rotation:
        record_lead_destination(destination)
    now = datetime.datetime.now().isoformat()
    with _connection() as conn:
        conn.execute(
            "INSERT INTO deliveries (leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, destination, updated_at) "
            "VALUES (?, ?, 1, 0, 0, ?, ?) "
            "ON CONFLICT(leadgen_id) DO UPDATE SET "
            "lead_id = excluded.lead_id, amocrm_ok = 1, "
            "destination = CASE WHEN excluded.destination != '' THEN excluded.destination ELSE deliveries.destination END, "
            "updated_at = excluded.updated_at",
            (str(leadgen_id), int(lead_id), destination, now),
        )


def record_delivery_status(
    leadgen_id: str,
    lead_id: Optional[int],
    amocrm_ok: bool,
    sheets_ok: bool,
    telegram_ok: bool,
    error: str = "",
    destination: str = "",
) -> None:
    """Record delivery outcome for all 3 channels: AmoCRM, Sheets, and Telegram."""
    if destination:
        record_lead_destination(destination)
    now = datetime.datetime.now().isoformat()
    lid = int(lead_id) if lead_id is not None else None
    with _connection() as conn:
        conn.execute(
            "INSERT INTO deliveries (leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, destination, last_error, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(leadgen_id) DO UPDATE SET "
            "lead_id = COALESCE(excluded.lead_id, deliveries.lead_id), "
            "amocrm_ok = excluded.amocrm_ok, "
            "sheets_ok = excluded.sheets_ok, "
            "telegram_ok = excluded.telegram_ok, "
            "destination = CASE WHEN excluded.destination != '' THEN excluded.destination ELSE deliveries.destination END, "
            "last_error = excluded.last_error, "
            "updated_at = excluded.updated_at",
            (str(leadgen_id), lid, int(amocrm_ok), int(sheets_ok), int(telegram_ok), destination, error, now),
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
            "SELECT leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, destination, retries, last_error, updated_at "
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


def is_delivery_complete(leadgen_id: str) -> bool:
    """Return True if lead has been delivered to all 3 channels (AmoCRM, Sheets, Telegram)."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT amocrm_ok, sheets_ok, telegram_ok FROM deliveries WHERE leadgen_id = ?",
            (str(leadgen_id),)
        ).fetchone()
    if not row:
        return False
    return bool(row[0] and row[1] and row[2])


def get_delivery_channel_status(leadgen_id: str) -> Dict[str, bool]:
    """Return status of individual channels for a lead (AmoCRM, Sheets, Telegram)."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT amocrm_ok, sheets_ok, telegram_ok FROM deliveries WHERE leadgen_id = ?",
            (str(leadgen_id),)
        ).fetchone()
    if not row:
        return {"amocrm": False, "sheets": False, "telegram": False}
    return {
        "amocrm": bool(row[0]),
        "sheets": bool(row[1]),
        "telegram": bool(row[2]),
    }


def try_claim_leadgen(leadgen_id: str, pid: int = 0) -> bool:
    """Atomic cross-process claim for a leadgen ID. Returns True if claimed, False if already claimed."""
    clean_id = str(leadgen_id or "").strip()
    if not clean_id:
        return False
    now = datetime.datetime.now().isoformat()
    with _connection() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO leadgen_claims (leadgen_id, claimed_at, pid) VALUES (?, ?, ?)",
            (clean_id, now, pid),
        )
        return cursor.rowcount > 0



