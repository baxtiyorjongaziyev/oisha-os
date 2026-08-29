"""
CRUD operations for conversation analysis records, failure tracking, and task write audits.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.core.salescoach_store.models import (
    ConversationAnalysisRecord,
    TaskWriteAudit,
    _ANALYSIS_COLUMNS,
    _decode_analysis_row,
    _maybe_await,
    _now_iso,
    _privacy_safe_analysis,
    _row_to_dict,
)

logger = logging.getLogger("TelegramSalesCoachStore")


class AnalysisOpsMixin:
    """Handles analysis persistence, approvals, fingerprinting, and audit logging."""

    async def record_analysis_failure(
        self,
        *,
        fingerprint: str,
        lead_id: int,
        telegram_user_hash: str,
        failure_code: str,
        attempts: int = 5,
    ) -> None:
        connection = await self._connection()
        now = datetime.now(timezone.utc)
        next_retry = now.timestamp() + min(3600, 60 * max(1, attempts))
        await self._execute(
            connection,
            """
            INSERT INTO salescoach_analysis_retry_queue (
                fingerprint, lead_id, telegram_user_hash, attempts,
                failure_code, next_retry_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                attempts = salescoach_analysis_retry_queue.attempts + excluded.attempts,
                failure_code = excluded.failure_code,
                next_retry_at = excluded.next_retry_at,
                updated_at = excluded.updated_at
            """,
            (
                fingerprint,
                int(lead_id),
                telegram_user_hash,
                max(1, int(attempts)),
                failure_code,
                datetime.fromtimestamp(next_retry, timezone.utc).isoformat(),
                now.isoformat(),
            ),
        )
        await self._commit(connection)

    async def clear_analysis_failure(self, fingerprint: str) -> None:
        connection = await self._connection()
        await self._execute(
            connection,
            "DELETE FROM salescoach_analysis_retry_queue WHERE fingerprint = ?",
            (fingerprint,),
        )
        await self._commit(connection)

    async def save_analysis(self, record: ConversationAnalysisRecord) -> int:
        connection = await self._connection()
        now = _now_iso()
        safe_analysis = _privacy_safe_analysis(record.analysis)
        await self._execute(
            connection,
            """
            INSERT INTO conversation_analyses (
                conversation_hash,
                telegram_user_hash,
                contact_id,
                lead_id,
                manager_id,
                fingerprint,
                overall_score,
                confidence,
                source_message_ids_json,
                rollout_mode,
                analysis_json,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                conversation_hash = excluded.conversation_hash,
                telegram_user_hash = excluded.telegram_user_hash,
                contact_id = excluded.contact_id,
                lead_id = excluded.lead_id,
                manager_id = excluded.manager_id,
                overall_score = excluded.overall_score,
                confidence = excluded.confidence,
                source_message_ids_json = excluded.source_message_ids_json,
                rollout_mode = excluded.rollout_mode,
                analysis_json = excluded.analysis_json,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                record.conversation_hash,
                record.telegram_user_hash,
                int(record.contact_id) if record.contact_id is not None else None,
                int(record.lead_id),
                str(record.manager_id),
                record.fingerprint,
                max(0, min(int(record.overall_score), 100)),
                max(0.0, min(float(record.confidence), 1.0)),
                json.dumps(record.source_message_ids, ensure_ascii=False),
                record.rollout_mode,
                json.dumps(safe_analysis, ensure_ascii=False),
                record.status,
                now,
                now,
            ),
        )
        await self._commit(connection)
        cursor = await self._execute(
            connection,
            "SELECT id FROM conversation_analyses WHERE fingerprint = ?",
            (record.fingerprint,),
        )
        row = await _maybe_await(cursor.fetchone())
        if row is None:
            raise RuntimeError("conversation_analysis_not_persisted")
        return int(row[0])

    async def get_analysis(self, analysis_id: int) -> dict[str, Any] | None:
        connection = await self._connection()
        cursor = await self._execute(
            connection,
            f"SELECT {', '.join(_ANALYSIS_COLUMNS)} FROM conversation_analyses WHERE id = ? LIMIT 1",  # nosec B608 -- fixed column allowlist
            (int(analysis_id),),
        )
        row = await _maybe_await(cursor.fetchone())
        if row is None:
            return None
        columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
        return _decode_analysis_row(row, columns or _ANALYSIS_COLUMNS)

    async def update_analysis_status(
        self,
        analysis_id: int,
        status: str,
    ) -> bool:
        allowed = {
            "analyzed",
            "pending",
            "processing",
            "approved",
            "rejected",
            "write_failed",
        }
        normalized = str(status or "").strip().lower()
        if normalized not in allowed:
            raise ValueError("invalid_conversation_analysis_status")

        connection = await self._connection()
        cursor = await self._execute(
            connection,
            "UPDATE conversation_analyses SET status = ?, updated_at = ? WHERE id = ?",
            (normalized, _now_iso(), int(analysis_id)),
        )
        await self._commit(connection)
        rowcount = getattr(cursor, "rowcount", None)
        if rowcount is None:
            return await self.get_analysis(analysis_id) is not None
        return int(rowcount) > 0

    async def claim_analysis_approval(self, analysis_id: int) -> bool:
        """Atomically move one pending analysis into approval processing."""
        connection = await self._connection()
        cursor = await self._execute(
            connection,
            """
            UPDATE conversation_analyses
            SET status = 'processing', updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (_now_iso(), int(analysis_id)),
        )
        await self._commit(connection)
        rowcount = getattr(cursor, "rowcount", None)
        if rowcount is not None and int(rowcount) >= 0:
            return int(rowcount) == 1
        refreshed = await self.get_analysis(analysis_id)
        return bool(refreshed and refreshed.get("status") == "processing")

    async def fingerprint_exists(self, fingerprint: str) -> bool:
        connection = await self._connection()
        cursor = await self._execute(
            connection,
            "SELECT 1 FROM conversation_analyses WHERE fingerprint = ? LIMIT 1",
            (fingerprint,),
        )
        return await _maybe_await(cursor.fetchone()) is not None

    async def task_key_exists(self, idempotency_key: str) -> bool:
        connection = await self._connection()
        cursor = await self._execute(
            connection,
            "SELECT 1 FROM salescoach_task_audit WHERE idempotency_key = ? LIMIT 1",
            (idempotency_key,),
        )
        return await _maybe_await(cursor.fetchone()) is not None

    async def claim_task_write(self, audit: TaskWriteAudit) -> bool:
        """Atomically reserve an idempotency key before any remote mutation."""
        connection = await self._connection()
        now = _now_iso()
        cursor = await self._execute(
            connection,
            """
            INSERT INTO salescoach_task_audit (
                idempotency_key, lead_id, task_type, conversation_fingerprint,
                amocrm_task_id, amocrm_note_id, verification_status,
                failure_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '', ?, 'claimed', '', ?, ?)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (
                audit.idempotency_key,
                int(audit.lead_id),
                audit.task_type,
                audit.conversation_fingerprint,
                audit.amocrm_note_id,
                audit.created_at,
                now,
            ),
        )
        await self._commit(connection)
        rowcount = getattr(cursor, "rowcount", None)
        if rowcount is not None and int(rowcount) >= 0:
            return int(rowcount) == 1
        changes = await self._execute(connection, "SELECT changes()")
        row = await _maybe_await(changes.fetchone())
        return bool(row and int(row[0]) == 1)

    async def record_task_write(self, audit: TaskWriteAudit) -> None:
        connection = await self._connection()
        now = _now_iso()
        await self._execute(
            connection,
            """
            INSERT INTO salescoach_task_audit (
                idempotency_key,
                lead_id,
                task_type,
                conversation_fingerprint,
                amocrm_task_id,
                amocrm_note_id,
                verification_status,
                failure_code,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(idempotency_key) DO UPDATE SET
                amocrm_task_id = excluded.amocrm_task_id,
                amocrm_note_id = excluded.amocrm_note_id,
                verification_status = excluded.verification_status,
                failure_code = excluded.failure_code,
                updated_at = excluded.updated_at
            """,
            (
                audit.idempotency_key,
                int(audit.lead_id),
                audit.task_type,
                audit.conversation_fingerprint,
                audit.amocrm_task_id,
                audit.amocrm_note_id,
                audit.verification_status,
                audit.failure_code,
                audit.created_at,
                now,
            ),
        )
        await self._commit(connection)

    async def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        connection = await self._connection()
        cursor = await self._execute(
            connection,
            f"""
            SELECT {', '.join(_ANALYSIS_COLUMNS)}
            FROM conversation_analyses
            ORDER BY updated_at DESC
            LIMIT ?
            """,  # nosec B608 -- fixed column allowlist
            (max(1, min(int(limit), 500)),),
        )
        rows = await _maybe_await(cursor.fetchall())
        columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
        return [
            decoded
            for row in rows or []
            if (decoded := _decode_analysis_row(row, columns or _ANALYSIS_COLUMNS))
        ]
