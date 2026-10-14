"""Lead CAPI intent in the existing durable delivery DB; no contact data stored."""
from __future__ import annotations

import sqlite3
import time


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS capi_lead_queue ("
        "leadgen_id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL, "
        "attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0)"
    )


def enqueue_in_checkpoint(conn: sqlite3.Connection, leadgen_id: str, lead_id: int) -> None:
    """Insert intent in the same transaction as its CRM checkpoint."""
    _ensure_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO capi_lead_queue (leadgen_id, lead_id) VALUES (?, ?)",
        (str(leadgen_id), int(lead_id)),
    )


def enqueue(leadgen_id: str, lead_id: int) -> None:
    from src.services.core.instagram.leadgen_delivery import _connection

    with _connection() as conn:
        enqueue_in_checkpoint(conn, leadgen_id, lead_id)


def pending(limit: int = 4) -> list[dict]:
    from src.services.core.instagram.leadgen_delivery import _connection

    with _connection() as conn:
        _ensure_table(conn)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT leadgen_id, lead_id FROM capi_lead_queue "
            "WHERE next_attempt <= ? ORDER BY next_attempt, rowid LIMIT ?",
            (time.time(), limit),
        ).fetchall()
    return [dict(row) for row in rows]


def complete(leadgen_id: str) -> None:
    from src.services.core.instagram.leadgen_delivery import _connection

    with _connection() as conn:
        _ensure_table(conn)
        conn.execute("DELETE FROM capi_lead_queue WHERE leadgen_id = ?", (str(leadgen_id),))


def retry_later(leadgen_id: str) -> None:
    from src.services.core.instagram.leadgen_delivery import _connection

    with _connection() as conn:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT attempts FROM capi_lead_queue WHERE leadgen_id = ?", (str(leadgen_id),),
        ).fetchone()
        if row is None:
            return
        delay = min(3600, 60 * (2 ** min(int(row[0]), 6)))
        conn.execute(
            "UPDATE capi_lead_queue SET attempts = attempts + 1, next_attempt = ? WHERE leadgen_id = ?",
            (time.time() + delay, str(leadgen_id)),
        )
