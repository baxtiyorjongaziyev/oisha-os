"""Checkpoint repository for tracking sync progress."""
from __future__ import annotations

import datetime
import structlog
from typing import Any, Dict, List, Optional

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class CheckpointRepository(BaseRepository):
    """Repository for checkpoint operations."""

    async def init_table(self) -> None:
        """Create chat_checkpoints table."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS chat_checkpoints (
                chat_id INTEGER PRIMARY KEY,
                last_processed_msg_id INTEGER,
                last_processed_at DATETIME
            )
        """)

    async def update_chat_checkpoint(self, chat_id: int, msg_id: int) -> None:
        """Update chat checkpoint."""
        if not chat_id or not msg_id:
            return
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = await self._get_conn()
        await conn.execute(
            """
            INSERT INTO chat_checkpoints (chat_id, last_processed_msg_id, last_processed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_processed_msg_id = MAX(chat_checkpoints.last_processed_msg_id, excluded.last_processed_msg_id),
                last_processed_at = excluded.last_processed_at
            """,
            (int(chat_id), int(msg_id), now),
        )
        await conn.commit()

    async def get_recent_chat_checkpoints(
        self, since_days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get recent chat checkpoints."""
        since_dt = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=since_days)
        ).isoformat()
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT chat_id, last_processed_msg_id, last_processed_at FROM chat_checkpoints "
            "WHERE last_processed_at >= ? ORDER BY last_processed_at DESC",
            (since_dt,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "chat_id": r[0],
                    "last_processed_msg_id": r[1] or 0,
                    "last_processed_at": r[2],
                }
                for r in rows
            ]

    async def get_checkpoint(
        self, external_id: Any, checkpoint_key: str
    ) -> Optional[Dict[str, Any]]:
        """Get a service checkpoint."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT id, external_id, checkpoint_key, status, last_notified_at, created_at "
            "FROM service_checkpoints WHERE external_id = ? AND checkpoint_key = ?",
            (str(external_id), str(checkpoint_key)),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "external_id": row[1],
                    "checkpoint_key": row[2],
                    "status": row[3],
                    "last_notified_at": row[4],
                    "created_at": row[5],
                }
            return None

    async def mark_checkpoint_notified(
        self, external_id: Any, checkpoint_key: str, status: str = "Pending"
    ) -> None:
        """Mark a checkpoint as notified."""
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            """
            INSERT INTO service_checkpoints (external_id, checkpoint_key, status, last_notified_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(external_id, checkpoint_key) DO UPDATE SET
                status = excluded.status,
                last_notified_at = excluded.last_notified_at
            """,
            (str(external_id), str(checkpoint_key), status, now, now),
        )
        await conn.commit()
