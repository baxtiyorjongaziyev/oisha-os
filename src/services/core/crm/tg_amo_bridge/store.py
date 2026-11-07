"""Message id mapping between Telegram and amoCRM chat (anti-echo + status)."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("TgAmoBridge.store")

_DDL = """
CREATE TABLE IF NOT EXISTS tg_amo_messages (
    amo_msg_id TEXT PRIMARY KEY,
    tg_msg_id INTEGER,
    account_key TEXT NOT NULL,
    tg_user_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
_IDX = "CREATE INDEX IF NOT EXISTS idx_tg_amo_tg ON tg_amo_messages(account_key, tg_msg_id)"


class MessageStore:
    def __init__(self, pool=None):
        self._pool = pool
        self._ready = False

    def _db(self):
        if self._pool is None:
            from src.database_pool import db_pool

            self._pool = db_pool
        return self._pool

    async def ensure(self) -> None:
        if self._ready:
            return
        db = self._db()
        await db.execute(_DDL)
        await db.execute(_IDX)
        self._ready = True

    async def record(
        self,
        amo_msg_id: str,
        tg_msg_id: Optional[int],
        account_key: str,
        tg_user_id: int,
        direction: str,
        status: str = "sent",
    ) -> None:
        await self.ensure()
        await self._db().execute(
            "INSERT OR REPLACE INTO tg_amo_messages "
            "(amo_msg_id, tg_msg_id, account_key, tg_user_id, direction, status) VALUES (?,?,?,?,?,?)",
            [amo_msg_id, tg_msg_id, account_key, tg_user_id, direction, status],
        )

    async def has_amo_msg(self, amo_msg_id: str) -> bool:
        await self.ensure()
        rows = await self._db().execute(
            "SELECT 1 FROM tg_amo_messages WHERE amo_msg_id = ? LIMIT 1", [amo_msg_id]
        )
        return bool(rows)

    async def has_tg_msg(self, account_key: str, tg_msg_id: int) -> bool:
        await self.ensure()
        rows = await self._db().execute(
            "SELECT 1 FROM tg_amo_messages WHERE account_key = ? AND tg_msg_id = ? LIMIT 1",
            [account_key, tg_msg_id],
        )
        return bool(rows)

    async def amo_id_for_tg(self, account_key: str, tg_msg_id: int) -> Optional[str]:
        await self.ensure()
        rows = await self._db().execute(
            "SELECT amo_msg_id FROM tg_amo_messages WHERE account_key = ? AND tg_msg_id = ? LIMIT 1",
            [account_key, tg_msg_id],
        )
        return rows[0][0] if rows else None

    async def set_status(self, amo_msg_id: str, status: str) -> None:
        await self.ensure()
        await self._db().execute(
            "UPDATE tg_amo_messages SET status = ? WHERE amo_msg_id = ?", [status, amo_msg_id]
        )
