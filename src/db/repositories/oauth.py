"""Repository for managing OAuth 2.0 tokens (Airtable, etc.)."""
import structlog
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json

from src.db.repositories.base import BaseRepository, _is_benign_schema_error

logger = structlog.get_logger()

class OAuthRepository(BaseRepository):
    async def _init_tables(self) -> None:
        conn = await self.get_connection()
        try:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                service_name TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                extra_data TEXT
            )
            """)
            await conn.commit()
        except Exception as e:
            if not _is_benign_schema_error(e):
                logger.error("[DB] Failed to init oauth_tokens table", error=str(e))

    async def save_tokens(
        self,
        service_name: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save or update OAuth tokens for a service."""
        conn = await self.get_connection()
        now = datetime.now(timezone.utc)
        extra_str = json.dumps(extra_data) if extra_data else None

        await conn.execute(
            """
            INSERT INTO oauth_tokens (service_name, access_token, refresh_token, expires_at, updated_at, extra_data)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(service_name) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,
                updated_at=excluded.updated_at,
                extra_data=excluded.extra_data
            """,
            (service_name, access_token, refresh_token, expires_at.isoformat(), now.isoformat(), extra_str),
        )
        await conn.commit()

    async def get_tokens(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored tokens for a service."""
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT access_token, refresh_token, expires_at, extra_data FROM oauth_tokens WHERE service_name = ?",
            (service_name,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            # parse expires_at back to datetime if it's a string, though sqlite might return str
            expires_str = row[2]
            try:
                if isinstance(expires_str, str):
                    expires_at = datetime.fromisoformat(expires_str)
                else:
                    expires_at = expires_str
            except Exception:
                expires_at = None

            extra_data = json.loads(row[3]) if row[3] else {}
            return {
                "access_token": row[0],
                "refresh_token": row[1],
                "expires_at": expires_at,
                "extra_data": extra_data,
            }
