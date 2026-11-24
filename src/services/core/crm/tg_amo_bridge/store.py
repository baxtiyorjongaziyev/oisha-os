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
_LINKS_DDL = """
CREATE TABLE IF NOT EXISTS tg_amo_chat_links (
    tg_user_id INTEGER PRIMARY KEY,
    amo_chat_id TEXT,
    phone TEXT,
    username TEXT,
    linked_contact_id INTEGER,
    linked_lead_id INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
_LINKS_PHONE_IDX = "CREATE INDEX IF NOT EXISTS idx_tg_amo_links_phone ON tg_amo_chat_links(phone)"
_MERGES_DDL = """
CREATE TABLE IF NOT EXISTS tg_amo_merges (
    source_lead_id INTEGER PRIMARY KEY,
    target_lead_id INTEGER NOT NULL,
    source_contact_id INTEGER,
    target_contact_id INTEGER,
    tg_user_id INTEGER,
    phone TEXT,
    status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


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
        await db.execute(_LINKS_DDL)
        await db.execute(_LINKS_PHONE_IDX)
        await db.execute(_MERGES_DDL)
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

    async def get_chat_link(self, tg_user_id: int) -> Optional[dict]:
        await self.ensure()
        rows = await self._db().execute(
            "SELECT tg_user_id, amo_chat_id, phone, username, linked_contact_id, linked_lead_id "
            "FROM tg_amo_chat_links WHERE tg_user_id = ? LIMIT 1",
            [int(tg_user_id)],
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "tg_user_id": r[0],
            "amo_chat_id": r[1],
            "phone": r[2],
            "username": r[3],
            "linked_contact_id": r[4],
            "linked_lead_id": r[5],
        }

    async def upsert_chat_link(
        self,
        tg_user_id: int,
        *,
        amo_chat_id: Optional[str] = None,
        phone: Optional[str] = None,
        username: Optional[str] = None,
        linked_contact_id: Optional[int] = None,
        linked_lead_id: Optional[int] = None,
    ) -> None:
        await self.ensure()
        existing = await self.get_chat_link(tg_user_id) or {}
        await self._db().execute(
            "INSERT OR REPLACE INTO tg_amo_chat_links "
            "(tg_user_id, amo_chat_id, phone, username, linked_contact_id, linked_lead_id, updated_at) "
            "VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            [
                int(tg_user_id),
                amo_chat_id if amo_chat_id is not None else existing.get("amo_chat_id"),
                phone if phone is not None else existing.get("phone"),
                username if username is not None else existing.get("username"),
                linked_contact_id if linked_contact_id is not None else existing.get("linked_contact_id"),
                linked_lead_id if linked_lead_id is not None else existing.get("linked_lead_id"),
            ],
        )

    async def list_chat_links_with_phone(self, limit: int = 200) -> list[dict]:
        await self.ensure()
        rows = await self._db().execute(
            "SELECT tg_user_id, amo_chat_id, phone, username, linked_contact_id, linked_lead_id "
            "FROM tg_amo_chat_links WHERE phone IS NOT NULL AND phone != '' "
            "ORDER BY updated_at DESC LIMIT ?",
            [max(1, int(limit))],
        )
        return [
            {
                "tg_user_id": r[0],
                "amo_chat_id": r[1],
                "phone": r[2],
                "username": r[3],
                "linked_contact_id": r[4],
                "linked_lead_id": r[5],
            }
            for r in (rows or [])
        ]

    async def get_merge_record(self, source_lead_id: int) -> Optional[dict]:
        await self.ensure()
        rows = await self._db().execute(
            "SELECT source_lead_id, target_lead_id, source_contact_id, target_contact_id, "
            "tg_user_id, phone, status, reason FROM tg_amo_merges WHERE source_lead_id = ? LIMIT 1",
            [int(source_lead_id)],
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "source_lead_id": r[0],
            "target_lead_id": r[1],
            "source_contact_id": r[2],
            "target_contact_id": r[3],
            "tg_user_id": r[4],
            "phone": r[5],
            "status": r[6],
            "reason": r[7],
        }

    async def record_merge(
        self,
        *,
        source_lead_id: int,
        target_lead_id: int,
        source_contact_id: Optional[int],
        target_contact_id: Optional[int],
        tg_user_id: Optional[int],
        phone: str,
        status: str,
        reason: str = "",
    ) -> None:
        await self.ensure()
        await self._db().execute(
            "INSERT OR REPLACE INTO tg_amo_merges "
            "(source_lead_id, target_lead_id, source_contact_id, target_contact_id, "
            "tg_user_id, phone, status, reason, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            [
                int(source_lead_id),
                int(target_lead_id),
                int(source_contact_id) if source_contact_id else None,
                int(target_contact_id) if target_contact_id else None,
                int(tg_user_id) if tg_user_id else None,
                str(phone or ""),
                str(status),
                str(reason or ""),
            ],
        )
