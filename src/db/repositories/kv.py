"""Key-Value store repository for settings and state management."""
from __future__ import annotations

import json
import structlog
from typing import Any, Optional

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class KVRepository(BaseRepository):
    """Repository for key-value settings store."""

    async def init_table(self) -> None:
        """Create kv_settings table."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS kv_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME
            )
        """)

    async def get_state(self, key: str, default: Any = None) -> Any:
        """Get a value from kv_settings."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT value FROM kv_settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                val = row[0]
                if val is None:
                    return default
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return val
            return default

    async def set_state(self, key: str, value: Any) -> None:
        """Set a value in kv_settings."""
        import datetime
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError, OverflowError):
            serialized = str(value)
        await conn.execute(
            "INSERT OR REPLACE INTO kv_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, serialized, now),
        )
        await conn.commit()
