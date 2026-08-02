"""Privacy-safe persistence for Telegram SalesCoach analyses and AmoCRM writes."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


_SENSITIVE_ANALYSIS_KEYS = {
    "conversation",
    "message_text",
    "messages",
    "raw_messages",
    "transcript",
}
_ANALYSIS_COLUMNS = [
    "id",
    "conversation_hash",
    "telegram_user_hash",
    "contact_id",
    "lead_id",
    "manager_id",
    "fingerprint",
    "overall_score",
    "confidence",
    "source_message_ids_json",
    "rollout_mode",
    "analysis_json",
    "status",
    "created_at",
    "updated_at",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _privacy_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _privacy_safe_value(item)
            for key, item in value.items()
            if str(key).strip().lower() not in _SENSITIVE_ANALYSIS_KEYS
        }
    if isinstance(value, list):
        return [_privacy_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_privacy_safe_value(item) for item in value]
    return value


def _privacy_safe_analysis(value: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively drop raw conversation fields before persistence."""
    return _privacy_safe_value(value)


def _row_to_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, Mapping):
        return dict(row)
    try:
        return dict(row)
    except (TypeError, ValueError):
        return dict(zip(columns, row, strict=True))


def _decode_analysis_row(row: Any, columns: list[str]) -> dict[str, Any]:
    item = _row_to_dict(row, columns)
    if not item:
        return {}
    try:
        item["source_message_ids"] = json.loads(
            item.pop("source_message_ids_json", "[]")
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        item["source_message_ids"] = []
    try:
        item["analysis"] = json.loads(item.pop("analysis_json", "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        item["analysis"] = {}
    return item


@dataclass(frozen=True)
class ConversationAnalysisRecord:
    conversation_hash: str
    telegram_user_hash: str
    lead_id: int
    manager_id: str
    fingerprint: str
    overall_score: int
    confidence: float
    source_message_ids: list[int]
    rollout_mode: str
    analysis: Mapping[str, Any]
    contact_id: int | None = None
    status: str = "analyzed"


@dataclass(frozen=True)
class TaskWriteAudit:
    idempotency_key: str
    lead_id: int
    task_type: str
    conversation_fingerprint: str
    amocrm_task_id: str = ""
    amocrm_note_id: str = ""
    verification_status: str = "pending"
    failure_code: str = ""
    created_at: str = field(default_factory=_now_iso)


class TelegramSalesCoachStore:
    """SQLite/libSQL-compatible store with no raw Telegram message content."""

    def __init__(self, db: Any):
        self.db = db

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
