from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import PendingOperation


def canonical_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(
        arguments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_digest(tool_name: str, arguments: dict[str, Any]) -> str:
    payload = f"{tool_name}\n{canonical_arguments(arguments)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class ApprovalStore:
    """Durable, atomic state for owner-approved Telegram mutations."""

    def __init__(self, path: str | Path = "data/telegram_mcp_approvals.db"):
        self.path = Path(path)
        self._lock = asyncio.Lock()

    def _connect(self) -> sqlite3.Connection:
        # Approval operations need their dedicated local database: the file path
        # is part of this store's durability and test-isolation contract.
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mcp_pending_operations (
                    id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending','executing','cancelled','succeeded','failed','expired')
                    ),
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approved_by INTEGER,
                    approved_at TEXT,
                    finished_at TEXT,
                    result_summary TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mcp_pending_status_expiry
                ON mcp_pending_operations(status, expires_at);
                CREATE TABLE IF NOT EXISTS mcp_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    actor_id INTEGER,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(operation_id) REFERENCES mcp_pending_operations(id)
                );
                """
            )

    async def create(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        requester: str,
        ttl_seconds: int,
        risk: str = "mutation",
    ) -> PendingOperation:
        operation_id = f"op_{secrets.token_urlsafe(18)}"
        created_at = utcnow()
        expires_at = created_at + timedelta(seconds=max(1, int(ttl_seconds)))
        canonical = canonical_arguments(arguments)
        digest = payload_digest(tool_name, arguments)
        async with self._lock:
            await asyncio.to_thread(
                self._create_sync,
                operation_id,
                tool_name,
                canonical,
                requester,
                digest,
                risk,
                created_at.isoformat(),
                expires_at.isoformat(),
            )
        return PendingOperation(
            id=operation_id,
            tool_name=tool_name,
            arguments=json.loads(canonical),
            requester=requester,
            payload_hash=digest,
            risk=risk,
            status="pending",
            created_at=created_at,
            expires_at=expires_at,
        )

    def _create_sync(self, *values: Any) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO mcp_pending_operations (
                    id, tool_name, arguments_json, requester, payload_hash,
                    risk, status, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                values,
            )
            self._audit(connection, values[0], "requested", None, values[5])
            connection.commit()

    async def get(self, operation_id: str) -> PendingOperation | None:
        return await asyncio.to_thread(self._get_sync, operation_id)

    def _get_sync(self, operation_id: str) -> PendingOperation | None:
        with closing(self._connect()) as connection:
            res = connection.execute(
                "SELECT * FROM mcp_pending_operations WHERE id = ?", (operation_id,)
            )
            row = res.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in res.description]
            row_dict = dict(zip(columns, row))
            return self._row_to_operation(row_dict)

    async def claim(
        self, operation_id: str, owner_id: int, expected_owner_id: int
    ) -> PendingOperation | None:
        if not expected_owner_id or owner_id != expected_owner_id:
            return None
        async with self._lock:
            return await asyncio.to_thread(
                self._claim_sync, operation_id, int(owner_id), utcnow().isoformat()
            )

    def _claim_sync(
        self, operation_id: str, owner_id: int, now_iso: str
    ) -> PendingOperation | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE mcp_pending_operations
                SET status = 'executing', approved_by = ?, approved_at = ?
                WHERE id = ? AND status = 'pending' AND expires_at > ?
                """,
                (owner_id, now_iso, operation_id, now_iso),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            self._audit(connection, operation_id, "approved", owner_id, "")
            res = connection.execute(
                "SELECT * FROM mcp_pending_operations WHERE id = ?", (operation_id,)
            )
            row = res.fetchone()
            columns = [desc[0] for desc in res.description]
            row_dict = dict(zip(columns, row))
            connection.commit()
            return self._row_to_operation(row_dict)

    async def cancel(
        self, operation_id: str, owner_id: int, expected_owner_id: int
    ) -> bool:
        if not expected_owner_id or owner_id != expected_owner_id:
            return False
        async with self._lock:
            return await asyncio.to_thread(
                self._cancel_sync, operation_id, int(owner_id), utcnow().isoformat()
            )

    def _cancel_sync(self, operation_id: str, owner_id: int, now_iso: str) -> bool:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE mcp_pending_operations
                SET status = 'cancelled', finished_at = ?
                WHERE id = ? AND status = 'pending' AND expires_at > ?
                """,
                (now_iso, operation_id, now_iso),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            self._audit(connection, operation_id, "cancelled", owner_id, "")
            connection.commit()
            return True

    async def finish(
        self, operation_id: str, status: str, result_summary: str = ""
    ) -> None:
        if status not in {"succeeded", "failed"}:
            raise ValueError("finish status must be succeeded or failed")
        summary = (result_summary or "")[:500]
        async with self._lock:
            await asyncio.to_thread(
                self._finish_sync,
                operation_id,
                status,
                summary,
                utcnow().isoformat(),
            )

    async def finish_notification_failure(
        self, operation_id: str, error_name: str
    ) -> None:
        """Fail a still-pending operation when owner notification cannot be sent."""
        async with self._lock:
            await asyncio.to_thread(
                self._finish_notification_failure_sync,
                operation_id,
                (error_name or "notification error")[:200],
                utcnow().isoformat(),
            )

    def _finish_notification_failure_sync(
        self, operation_id: str, error_name: str, now_iso: str
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE mcp_pending_operations
                SET status = 'failed', result_summary = ?, finished_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (error_name, now_iso, operation_id),
            )
            if cursor.rowcount == 1:
                self._audit(
                    connection, operation_id, "notification_failed", None, error_name
                )
                connection.commit()
            else:
                connection.rollback()

    def _finish_sync(
        self, operation_id: str, status: str, summary: str, now_iso: str
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE mcp_pending_operations
                SET status = ?, result_summary = ?, finished_at = ?
                WHERE id = ? AND status = 'executing'
                """,
                (status, summary, now_iso, operation_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise RuntimeError("operation is not executing")
            self._audit(connection, operation_id, status, None, summary)
            connection.commit()

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        operation_id: str,
        event: str,
        actor_id: int | None,
        details: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO mcp_audit_events (
                operation_id, event, actor_id, details, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (operation_id, event, actor_id, (details or "")[:500], utcnow().isoformat()),
        )

    @staticmethod
    def _row_to_operation(row: dict) -> PendingOperation:
        return PendingOperation(
            id=row["id"],
            tool_name=row["tool_name"],
            arguments=json.loads(row["arguments_json"]),
            requester=row["requester"],
            payload_hash=row["payload_hash"],
            risk=row["risk"],
            status=row["status"],
            created_at=_parse_datetime(row["created_at"]),
            expires_at=_parse_datetime(row["expires_at"]),
            approved_by=row["approved_by"],
        )
