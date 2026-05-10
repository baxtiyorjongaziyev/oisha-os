"""
retry_queue — Persistent retry queue for failed tool actions.

When AgentVerifier reports a failure, the caller enqueues the failed action
here. A background worker drains the queue with exponential backoff (3 attempts
max). After the 3rd failure the action is marked `dead` and the owner is
notified via a pluggable alert function.

API:
    from src.services.core.retry_queue import RetryQueue

    queue = RetryQueue(db, alert_fn=owner_alert)
    await queue.enqueue(action)           # add to queue
    await queue.drain_once()             # process one pass (call from scheduler)

Schema (SQLite):
    retry_queue(id, action_name, payload_json, attempt, max_attempts,
                status, next_retry_at, error, created_at, updated_at)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

Status = str  # "pending" | "retrying" | "succeeded" | "dead"

BASE_BACKOFF_SEC = 30   # 30s, 60s, 120s for attempts 1-3
MAX_ATTEMPTS = 3


class RetryQueue:
    """SQLite-backed persistent retry queue with exponential backoff."""

    def __init__(
        self,
        db: Any,
        executor_fn: Optional[Callable] = None,
        alert_fn: Optional[Callable] = None,
    ):
        """
        Args:
            db: Database singleton with get_conn() context manager.
            executor_fn: async callable(action_name, payload) → {success, error}.
                         If None, actions are logged only (useful in tests).
            alert_fn: async callable(msg: str) for owner escalation alerts.
        """
        self._db = db
        self._executor = executor_fn
        self._alert = alert_fn
        self._ensured = False

    async def _ensure_table(self) -> None:
        if self._ensured:
            return
        try:
            async with self._db.get_conn() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS retry_queue (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        action_name     TEXT    NOT NULL,
                        payload_json    TEXT    NOT NULL,
                        attempt         INTEGER DEFAULT 0,
                        max_attempts    INTEGER DEFAULT 3,
                        status          TEXT    DEFAULT 'pending',
                        next_retry_at   TEXT    DEFAULT (datetime('now')),
                        error           TEXT,
                        created_at      TEXT    DEFAULT (datetime('now')),
                        updated_at      TEXT    DEFAULT (datetime('now'))
                    )
                    """
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rq_status_next "
                    "ON retry_queue(status, next_retry_at)"
                )
                await conn.commit()
            self._ensured = True
        except Exception as exc:
            logger.warning(f"[RetryQueue] table init failed: {exc}")

    async def enqueue(
        self,
        action_name: str,
        payload: Dict[str, Any],
        max_attempts: int = MAX_ATTEMPTS,
    ) -> Optional[int]:
        """Insert a new action into the queue. Returns row id or None on error."""
        await self._ensure_table()
        try:
            async with self._db.get_conn() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO retry_queue
                        (action_name, payload_json, max_attempts, status, next_retry_at)
                    VALUES (?, ?, ?, 'pending', datetime('now'))
                    """,
                    (action_name, json.dumps(payload, ensure_ascii=False), max_attempts),
                )
                await conn.commit()
                row_id: int = cursor.lastrowid
                logger.info(f"[RetryQueue] enqueued #{row_id} {action_name}")
                return row_id
        except Exception as exc:
            logger.error(f"[RetryQueue] enqueue failed: {exc}")
            return None

    async def drain_once(self) -> int:
        """Process all due pending/retrying actions. Returns count attempted."""
        await self._ensure_table()
        try:
            async with self._db.get_conn() as conn:
                cursor = await conn.execute(
                    """
                    SELECT id, action_name, payload_json, attempt, max_attempts
                    FROM retry_queue
                    WHERE status IN ('pending', 'retrying')
                      AND next_retry_at <= datetime('now')
                    ORDER BY next_retry_at
                    LIMIT 20
                    """
                )
                rows = await cursor.fetchall()
        except Exception as exc:
            logger.error(f"[RetryQueue] drain fetch failed: {exc}")
            return 0

        count = 0
        for row_id, action_name, payload_json, attempt, max_attempts in rows:
            count += 1
            payload = {}
            try:
                payload = json.loads(payload_json)
            except Exception:
                pass

            new_attempt = attempt + 1
            success, error = await self._try_execute(action_name, payload)

            if success:
                await self._update(row_id, "succeeded", new_attempt, None, None)
                logger.info(f"[RetryQueue] #{row_id} {action_name} succeeded on attempt {new_attempt}")
            elif new_attempt >= max_attempts:
                await self._update(row_id, "dead", new_attempt, None, error)
                logger.error(f"[RetryQueue] #{row_id} {action_name} dead after {new_attempt} attempts: {error}")
                await self._escalate(action_name, payload, error, new_attempt)
            else:
                delay_sec = BASE_BACKOFF_SEC * (2 ** (new_attempt - 1))
                await self._update_retrying(row_id, new_attempt, error, delay_sec)
                logger.warning(
                    f"[RetryQueue] #{row_id} {action_name} attempt {new_attempt} failed, "
                    f"retry in {delay_sec}s: {error}"
                )

        return count

    async def _try_execute(
        self, action_name: str, payload: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        if self._executor is None:
            logger.debug(f"[RetryQueue] no executor — dry-run for {action_name}")
            return True, None
        try:
            result = await self._executor(action_name, payload)
            if isinstance(result, dict):
                return bool(result.get("success", True)), result.get("error")
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def _update(
        self,
        row_id: int,
        status: Status,
        attempt: int,
        next_retry_sql: Optional[str],
        error: Optional[str],
    ) -> None:
        try:
            async with self._db.get_conn() as conn:
                await conn.execute(
                    """
                    UPDATE retry_queue
                    SET status = ?, attempt = ?, error = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (status, attempt, error, row_id),
                )
                await conn.commit()
        except Exception as exc:
            logger.debug(f"[RetryQueue] _update failed: {exc}")

    async def _update_retrying(
        self,
        row_id: int,
        attempt: int,
        error: Optional[str],
        delay_sec: int,
    ) -> None:
        try:
            async with self._db.get_conn() as conn:
                await conn.execute(
                    f"""
                    UPDATE retry_queue
                    SET status = 'retrying',
                        attempt = ?,
                        error = ?,
                        next_retry_at = datetime('now', '+{delay_sec} seconds'),
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (attempt, error, row_id),
                )
                await conn.commit()
        except Exception as exc:
            logger.debug(f"[RetryQueue] _update_retrying failed: {exc}")

    async def _escalate(
        self,
        action_name: str,
        payload: Dict[str, Any],
        error: Optional[str],
        attempts: int,
    ) -> None:
        msg = (
            f"[Oisha] Dead action after {attempts} retries:\n"
            f"Action: `{action_name}`\n"
            f"Error: {error}\n"
            f"Payload: {json.dumps(payload, ensure_ascii=False)[:300]}"
        )
        if self._alert:
            try:
                await self._alert(msg)
            except Exception as exc:
                logger.error(f"[RetryQueue] alert failed: {exc}")
        else:
            logger.critical(f"[RetryQueue] DEAD ACTION — {msg}")

    async def stats(self) -> Dict[str, int]:
        """Return counts by status for monitoring."""
        await self._ensure_table()
        try:
            async with self._db.get_conn() as conn:
                cursor = await conn.execute(
                    "SELECT status, COUNT(*) FROM retry_queue GROUP BY status"
                )
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}
        except Exception:
            return {}
