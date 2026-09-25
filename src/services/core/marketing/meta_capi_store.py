"""Idempotent `capi_events` jadvali — har (leadgen_id, event_name) Meta'ga bir marta.

Barcha yozuvlar `database_pool.db_pool` orqali (Turso). `claim_event` atomik:
INSERT ... ON CONFLICT ... RETURNING — qator qaytsa, shu jarayon yuborish huquqini oldi.
"""
from __future__ import annotations

import datetime
from typing import Optional

_CREATE = (
    "CREATE TABLE IF NOT EXISTS capi_events ("
    "leadgen_id TEXT NOT NULL, event_name TEXT NOT NULL, amo_lead_id INTEGER, "
    "source TEXT DEFAULT '', status TEXT NOT NULL, error TEXT DEFAULT '', "
    "updated_at TEXT NOT NULL, sent_at TEXT, "
    "PRIMARY KEY (leadgen_id, event_name))"
)
# Jarayon qulab `pending` qolib ketgan yozuvni shu vaqtdan keyin qayta olish mumkin.
_STALE_PENDING = datetime.timedelta(minutes=10)
_table_ready = False


def _pool():
    from src.database_pool import db_pool
    return db_pool


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def ensure_table() -> None:
    global _table_ready
    if not _table_ready:
        await _pool().execute(_CREATE)
        _table_ready = True


async def claim_event(
    leadgen_id: str, event_name: str, amo_lead_id: Optional[int] = None, source: str = "",
) -> bool:
    """True — yuborish huquqi olindi; False — allaqachon yuborilgan yoki jarayonda."""
    await ensure_table()
    now = _now()
    stale_before = (now - _STALE_PENDING).isoformat()
    rows = await _pool().execute(
        "INSERT INTO capi_events (leadgen_id, event_name, amo_lead_id, source, status, updated_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?) "
        "ON CONFLICT(leadgen_id, event_name) DO UPDATE SET "
        "status = 'pending', error = '', updated_at = excluded.updated_at, "
        "source = excluded.source, "
        "amo_lead_id = COALESCE(excluded.amo_lead_id, capi_events.amo_lead_id) "
        "WHERE capi_events.status = 'failed' "
        "OR (capi_events.status = 'pending' AND capi_events.updated_at < ?) "
        "RETURNING leadgen_id",
        [str(leadgen_id), event_name, amo_lead_id, source, now.isoformat(), stale_before],
    )
    return bool(rows)


async def mark_result(leadgen_id: str, event_name: str, ok: bool, error: str = "") -> None:
    now = _now().isoformat()
    await _pool().execute(
        "UPDATE capi_events SET status = ?, error = ?, updated_at = ?, "
        "sent_at = CASE WHEN ? THEN ? ELSE sent_at END "
        "WHERE leadgen_id = ? AND event_name = ?",
        ["sent" if ok else "failed", (error or "")[:500], now, int(ok), now,
         str(leadgen_id), event_name],
    )


async def get_event_status(leadgen_id: str, event_name: str) -> Optional[str]:
    await ensure_table()
    rows = await _pool().execute(
        "SELECT status FROM capi_events WHERE leadgen_id = ? AND event_name = ?",
        [str(leadgen_id), event_name],
    )
    return str(rows[0]["status"]) if rows else None
