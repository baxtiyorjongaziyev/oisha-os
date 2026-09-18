"""Reklama (ad_id) nomini mahalliy keshlaydi.

Bitta reklama/video ko'p kunlab ishlab, o'nlab lead keltirishi mumkin —
har bir lead uchun Meta'ga so'rov yubormaslik uchun nom bir marta olinib,
mahalliy SQLite'da saqlanadi (`data/meta_ad_names.db`).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "meta_ad_names.db"
_TTL_DAYS = 14  # reklama nomi kamdan-kam o'zgaradi, lekin abadiy ham keshlanmasin

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ad_names (
    ad_id TEXT PRIMARY KEY,
    ad_name TEXT,
    fetched_at TEXT
)
"""


@contextmanager
def _connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(_CREATE_TABLE)
        yield conn


def get_cached_name(ad_id: str) -> Optional[str]:
    """Kesh ichida bor va eskirmagan bo'lsa qaytaradi, aks holda None."""
    if not ad_id:
        return None
    with _connection() as conn:
        row = conn.execute(
            "SELECT ad_name FROM ad_names WHERE ad_id = ? "
            "AND fetched_at >= datetime('now', ?)",
            (ad_id, f"-{_TTL_DAYS} days"),
        ).fetchone()
    return row["ad_name"] if row else None


def save_name(ad_id: str, ad_name: str, fetched_at: str) -> None:
    if not ad_id:
        return
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO ad_names (ad_id, ad_name, fetched_at) VALUES (?, ?, ?)
            ON CONFLICT(ad_id) DO UPDATE SET ad_name=excluded.ad_name, fetched_at=excluded.fetched_at
            """,
            (ad_id, ad_name, fetched_at),
        )
