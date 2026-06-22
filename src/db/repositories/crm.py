"""CRM sync repository for AmoCRM operations."""
from __future__ import annotations

import datetime
import structlog
from typing import Any, Dict, List, Optional

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class CRMRepository(BaseRepository):
    """Repository for CRM sync operations."""

    async def init_table(self) -> None:
        """Create crm_sync_status table."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS crm_sync_status (
                user_id INTEGER PRIMARY KEY,
                amo_lead_id INTEGER,
                status TEXT DEFAULT 'synced',
                synced_at DATETIME
            )
        """)

    async def is_crm_synced(self, user_id: int) -> bool:
        """Check if user is synced to CRM."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT crm_synced FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

    async def mark_crm_synced(self, user_id: int) -> bool:
        """Mark user as CRM synced."""
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        cursor = await conn.execute(
            "UPDATE users SET crm_synced = 1, processed_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        if cursor.rowcount == 0:
            await conn.execute(
                """
                INSERT INTO users (user_id, first_name, crm_synced, processed_at, created_at, last_seen)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (user_id, f"User {user_id}", now, now, now),
            )
        await conn.commit()
        return True

    async def get_recent_active_leads(
        self, hours: int = 72, limit: int = 12
    ) -> List[Dict[str, Any]]:
        """Return recently active leads with their latest client message."""
        cutoff = (
            datetime.datetime.now()
            - datetime.timedelta(hours=max(1, int(hours)))
        ).isoformat()
        conn = await self._get_conn()
        async with conn.execute(
            """
            SELECT
                u.user_id, u.first_name, u.username, u.phone,
                u.business_type, u.region, u.brand_name, u.service_type,
                u.intent, u.meeting_time, u.meeting_status,
                u.journey_stage, u.journey_status, u.journey_next_action,
                u.close_probability, u.last_client_message_at,
                u.last_ai_message_at, u.lifecycle_updated_at,
                css.amo_lead_id,
                (
                    SELECT ml.message_text
                    FROM message_logs ml
                    WHERE ml.user_id = u.user_id
                      AND COALESCE(ml.is_ai_reply, 0) = 0
                      AND ml.message_text IS NOT NULL
                      AND ml.message_text != ''
                    ORDER BY ml.created_at DESC, ml.id DESC
                    LIMIT 1
                ) AS last_client_message
            FROM users u
            LEFT JOIN crm_sync_status css ON u.user_id = css.user_id
            WHERE u.last_client_message_at IS NOT NULL
              AND u.last_client_message_at >= ?
            ORDER BY u.last_client_message_at DESC
            LIMIT ?
            """,
            (cutoff, max(1, int(limit))),
        ) as cursor:
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
