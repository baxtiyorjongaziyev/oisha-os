"""Durable CRM checkpoints for Telegram delivery retries."""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager
from pathlib import Path

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
        yield conn


def get_crm_checkpoint(leadgen_id: str) -> int | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT lead_id FROM deliveries WHERE leadgen_id = ?", (leadgen_id,)
        ).fetchone()
    return int(row[0]) if row else None


def save_crm_checkpoint(leadgen_id: str, lead_id: int) -> None:
    with _connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deliveries VALUES (?, ?)",
            (leadgen_id, int(lead_id)),
        )
