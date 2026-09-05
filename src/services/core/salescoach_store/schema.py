"""
Database initialization and execution primitives for SalesCoach store.
"""
from __future__ import annotations

import logging
from typing import Any

from src.services.core.salescoach_store.models import _maybe_await

logger = logging.getLogger("TelegramSalesCoachStore")


class SchemaMixin:
    """Handles table creation, schema migration, and DB execution helpers."""

    async def _connection(self) -> Any:
        return await _maybe_await(self.db.get_connection())

    async def _execute(
        self,
        connection: Any,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> Any:
        return await _maybe_await(connection.execute(sql, params))

    async def _commit(self, connection: Any) -> None:
        commit = getattr(connection, "commit", None)
        if callable(commit):
            await _maybe_await(commit())

    async def initialize(self) -> None:
        connection = await self._connection()
        await self._execute(
            connection,
            """
            CREATE TABLE IF NOT EXISTS conversation_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_hash TEXT NOT NULL,
                telegram_user_hash TEXT NOT NULL,
                contact_id INTEGER,
                lead_id INTEGER NOT NULL,
                manager_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                overall_score INTEGER NOT NULL,
                confidence REAL NOT NULL,
                source_message_ids_json TEXT NOT NULL,
                rollout_mode TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'analyzed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        )
        await self._execute(
            connection,
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_analyses_lead
            ON conversation_analyses(lead_id, created_at)
            """,
        )
        columns_cursor = await self._execute(
            connection,
            "PRAGMA table_info(conversation_analyses)",
        )
        existing_columns = {
            str(row[1])
            for row in (await _maybe_await(columns_cursor.fetchall()) or [])
        }
        if "contact_id" not in existing_columns:
            await self._execute(
                connection,
                "ALTER TABLE conversation_analyses ADD COLUMN contact_id INTEGER",
            )
        await self._execute(
            connection,
            """
            CREATE TABLE IF NOT EXISTS salescoach_task_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                lead_id INTEGER NOT NULL,
                task_type TEXT NOT NULL,
                conversation_fingerprint TEXT NOT NULL,
                amocrm_task_id TEXT NOT NULL DEFAULT '',
                amocrm_note_id TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'pending',
                failure_code TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        )
        await self._execute(
            connection,
            """
            CREATE INDEX IF NOT EXISTS idx_salescoach_task_audit_lead
            ON salescoach_task_audit(lead_id, task_type)
            """,
        )
        await self._execute(
            connection,
            """
            CREATE TABLE IF NOT EXISTS salescoach_analysis_retry_queue (
                fingerprint TEXT PRIMARY KEY,
                lead_id INTEGER NOT NULL,
                telegram_user_hash TEXT NOT NULL,
                contact_id INTEGER,
                attempts INTEGER NOT NULL DEFAULT 0,
                failure_code TEXT NOT NULL,
                next_retry_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        )
        await self._commit(connection)
