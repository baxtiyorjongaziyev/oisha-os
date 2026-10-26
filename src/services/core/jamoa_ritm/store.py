"""Hamroh xotirasi: jamoa guruhidagi xabarlar va jadval yuborilganlik jurnali.

Barcha yozuvlar ``database_pool.db_pool`` orqali o'tadi (Turso/SQLite). Testlar uchun
``execute(query, params)`` va ``commit()`` ga ega istalgan async obyekt berilishi mumkin.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_TEXT = 2000
ROLE_MEMBER = "azo"      # jamoa a'zosining xabari
ROLE_HAMROH = "hamroh"   # Hamroh'ning mention'ga javobi
ROLE_RITM = "ritm"       # jadval bo'yicha yuborilgan ritm xabari

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS jamoa_xabarlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        message_id INTEGER,
        user_id INTEGER,
        user_name TEXT,
        text TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'azo',
        created_at INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_jamoa_xabarlar_chat_time "
    "ON jamoa_xabarlar(chat_id, created_at)",
    """
    CREATE TABLE IF NOT EXISTS jamoa_ritm_log (
        slot TEXT NOT NULL,
        sana TEXT NOT NULL,
        sent_at INTEGER NOT NULL,
        PRIMARY KEY (slot, sana)
    )
    """,
)


def _row_get(row: Any, key: str, index: int) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


class JamoaStore:
    def __init__(self, db: Any = None):
        self._db = db
        self._ready = False

    def _conn(self) -> Any:
        if self._db is None:
            from src.database_pool import db_pool

            self._db = db_pool
        return self._db

    async def _exec(self, sql: str, params: tuple = (), *, write: bool = False) -> list:
        db = self._conn()
        rows = await db.execute(sql, list(params))
        if write:
            await db.commit()
        return list(rows or [])

    async def initialize(self) -> None:
        if self._ready:
            return
        for statement in _SCHEMA:
            await self._exec(statement, write=True)
        self._ready = True

    async def save_message(
        self,
        *,
        chat_id: int,
        text: str,
        user_id: Optional[int] = None,
        user_name: str = "",
        message_id: Optional[int] = None,
        role: str = ROLE_MEMBER,
        ts: Optional[int] = None,
    ) -> None:
        clean = (text or "").strip()
        if not clean:
            return
        await self.initialize()
        await self._exec(
            "INSERT INTO jamoa_xabarlar "
            "(chat_id, message_id, user_id, user_name, text, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                int(chat_id),
                message_id,
                user_id,
                (user_name or "")[:120],
                clean[:MAX_TEXT],
                role,
                int(ts if ts is not None else time.time()),
            ),
            write=True,
        )

    async def recent_messages(self, chat_id: int, since_ts: int, limit: int = 300) -> list[dict]:
        """``since_ts`` dan keyingi xabarlar, eskisidan yangisiga (oxirgi ``limit`` tasi)."""
        await self.initialize()
        rows = await self._exec(
            "SELECT user_name, text, role, created_at FROM jamoa_xabarlar "
            "WHERE chat_id = ? AND created_at >= ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (int(chat_id), int(since_ts), int(limit)),
        )
        items = [
            {
                "user_name": _row_get(r, "user_name", 0) or "",
                "text": _row_get(r, "text", 1) or "",
                "role": _row_get(r, "role", 2) or ROLE_MEMBER,
                "created_at": int(_row_get(r, "created_at", 3) or 0),
            }
            for r in rows
        ]
        items.reverse()
        return items

    async def was_sent(self, slot: str, sana: str) -> bool:
        await self.initialize()
        rows = await self._exec(
            "SELECT 1 FROM jamoa_ritm_log WHERE slot = ? AND sana = ?", (slot, sana)
        )
        return bool(rows)

    async def mark_sent(self, slot: str, sana: str) -> None:
        await self.initialize()
        await self._exec(
            "INSERT OR IGNORE INTO jamoa_ritm_log (slot, sana, sent_at) VALUES (?, ?, ?)",
            (slot, sana, int(time.time())),
            write=True,
        )

    async def prune(self, older_than_ts: int) -> None:
        """Eski xabarlarni o'chiradi (xotira cheksiz o'smasin)."""
        await self.initialize()
        await self._exec(
            "DELETE FROM jamoa_xabarlar WHERE created_at < ?", (int(older_than_ts),), write=True
        )
