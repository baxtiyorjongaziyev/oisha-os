"""Message repository for message-related database operations."""
from __future__ import annotations

import structlog
from typing import Any, Dict, List

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class MessageRepository(BaseRepository):
    """Repository for message operations."""

    async def init_tables(self) -> None:
        """Create message-related tables."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                is_ai BOOLEAN,
                created_at DATETIME
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_text TEXT,
                is_ai_reply BOOLEAN,
                created_at DATETIME
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS chat_summaries (
                user_id INTEGER PRIMARY KEY,
                summary TEXT,
                updated_at DATETIME
            )
        """)

        # Indexes
        await self._execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
        await self._execute("CREATE INDEX IF NOT EXISTS idx_message_logs_user_ai_created ON message_logs(user_id, is_ai_reply, created_at)")

    async def log_message(self, user_id: int, text: str, is_ai: bool = False) -> None:
        """Log a single message."""
        import datetime
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            "INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)",
            (user_id, text, is_ai, now),
        )
        if is_ai:
            await conn.execute(
                "UPDATE users SET last_ai_message_at = ?, last_seen = COALESCE(last_seen, ?) WHERE user_id = ?",
                (now, now, user_id),
            )
        else:
            await conn.execute(
                "UPDATE users SET last_client_message_at = ?, last_seen = COALESCE(last_seen, ?) WHERE user_id = ?",
                (now, now, user_id),
            )
        await conn.commit()

    async def log_messages_batch(self, messages_data: List[tuple]) -> None:
        """Log multiple messages in batch."""
        if not messages_data:
            return
        conn = await self._get_conn()
        await conn.executemany(
            "INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)",
            messages_data,
        )
        await conn.commit()

    async def get_recent_messages(self, user_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get recent messages for a user formatted for Gemini."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT message_text, is_ai_reply FROM message_logs WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            history = []
            for text, is_ai in reversed(rows):
                role = "model" if is_ai else "user"
                if text.startswith("ERROR:"):
                    continue
                history.append({"role": role, "parts": [{"text": text}]})
            if history and history[0]["role"] == "model":
                history.pop(0)
            sanitized = []
            last_role = None
            for entry in history:
                if entry["role"] != last_role:
                    sanitized.append(entry)
                    last_role = entry["role"]
            return sanitized

    async def get_chat_summary(self, user_id: int) -> str | None:
        """Get chat summary for a user."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT summary FROM chat_summaries WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_chat_summary(self, user_id: int, summary: str) -> bool:
        """Set chat summary for a user."""
        import datetime
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            "INSERT OR REPLACE INTO chat_summaries (user_id, summary, updated_at) VALUES (?, ?, ?)",
            (user_id, summary, now),
        )
        await conn.commit()
        return True

    async def get_daily_chats_summary(self) -> Dict[int, Dict[str, Any]]:
        """Get daily chat summaries for all users."""
        import datetime
        one_day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        conn = await self._get_conn()
        query = """
            SELECT ml.user_id, u.first_name, u.username, ml.message_text, ml.is_ai_reply, ml.created_at
            FROM message_logs ml LEFT JOIN users u ON ml.user_id = u.user_id
            WHERE ml.created_at >= ? ORDER BY ml.user_id, ml.created_at ASC
        """
        async with conn.execute(query, (one_day_ago,)) as cursor:
            rows = await cursor.fetchall()
            chats = {}
            for uid, name, uname, text, is_ai, time in rows:
                if uid not in chats:
                    chats[uid] = {
                        "name": name or f"User_{uid}",
                        "username": uname or "n/a",
                        "messages": [],
                    }
                role = "OISHA" if is_ai else "Client"
                chats[uid]["messages"].append(f"{role} ({time}): {text}")
            return chats

    async def get_recent_all_messages(self, limit: int = 50) -> List[tuple]:
        """Get recent messages from all users."""
        conn = await self._get_conn()
        query = """
            SELECT user_id, message_text, is_ai_reply, created_at
            FROM message_logs
            WHERE message_text IS NOT NULL AND message_text != ''
            ORDER BY created_at DESC
            LIMIT ?
        """
        async with conn.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [(r[0], r[1], r[2], r[3]) for r in reversed(rows)]

    async def get_stats(self) -> Dict[str, int]:
        """Get basic stats."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM message_logs)"
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"total_users": 0, "total_messages": 0}
            return {"total_users": row[0], "total_messages": row[1]}

    async def get_today_stats(self) -> Dict[str, int]:
        """Get today's stats."""
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = await self._get_conn()
        async with conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users WHERE date(created_at) = ?),
                (SELECT COUNT(*) FROM message_logs WHERE date(created_at) = ?)
            """,
            (today, today),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"leads_found": 0, "messages_synced": 0}
            return {
                "leads_found": row[0] or 0,
                "messages_synced": row[1] or 0,
            }
