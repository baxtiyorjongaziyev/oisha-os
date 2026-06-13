from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

from src.services.erp.models import ERPAction
from src.services.erp.repository import ERPRepository
from src.time_utils import get_local_now


@dataclass(frozen=True)
class QueueItem:
    action: dict[str, Any]
    attempt_id: str
    attempt_number: int
    worker_id: str


class ActionQueue:
    """Durable at-least-once queue backed by canonical ERP tables."""

    def __init__(self, repo: ERPRepository):
        self.repo = repo

    async def enqueue(self, action: ERPAction) -> bool:
        created = await self.repo.create_action(action)
        if not created:
            return False
        now = get_local_now().isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            "UPDATE erp_actions SET available_at = ?, updated_at = ? WHERE action_id = ?",
            (now, now, action.action_id),
        )
        await conn.commit()
        return True

    async def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 60,
    ) -> Optional[QueueItem]:
        await self.release_expired_leases()
        now = get_local_now()
        now_iso = now.isoformat()
        conn = await self.repo.db.get_connection()
        async with conn.execute(
            """
            SELECT action_id
            FROM erp_actions
            WHERE status IN ('pending', 'retrying')
              AND (available_at IS NULL OR available_at <= ?)
            ORDER BY created_at, action_id
            LIMIT 1
            """,
            (now_iso,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None

        action_id = str(row[0])
        lease_expires_at = (now + timedelta(seconds=max(1, lease_seconds))).isoformat()
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'executing',
                lease_owner = ?,
                lease_expires_at = ?,
                attempt_count = attempt_count + 1,
                updated_at = ?
            WHERE action_id = ? AND status IN ('pending', 'retrying')
            """,
            (worker_id, lease_expires_at, now_iso, action_id),
        )
        await conn.commit()
        action = await self.repo.get_action(action_id)
        if not action or action["status"] != "executing":
            return None

        attempt_number = int(action["attempt_count"])
        attempt_id = f"attempt-{uuid.uuid4().hex}"
        await conn.execute(
            """
            INSERT INTO erp_action_attempts (
                attempt_id, action_id, attempt_number, status,
                result_json, error, started_at, finished_at
            ) VALUES (?, ?, ?, 'executing', '{}', NULL, ?, NULL)
            """,
            (attempt_id, action_id, attempt_number, now_iso),
        )
        await conn.commit()
        return QueueItem(
            action=action,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            worker_id=worker_id,
        )

    async def release_expired_leases(self) -> int:
        now = get_local_now().isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_action_attempts
            SET status = 'lease_expired',
                error = 'worker_lease_expired',
                finished_at = ?
            WHERE status = 'executing'
              AND action_id IN (
                  SELECT action_id FROM erp_actions
                  WHERE status = 'executing'
                    AND lease_expires_at IS NOT NULL
                    AND lease_expires_at <= ?
              )
            """,
            (now, now),
        )
        cursor = await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'retrying',
                available_at = ?,
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = 'worker_lease_expired',
                updated_at = ?
            WHERE status = 'executing'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= ?
            """,
            (now, now, now),
        )
        await conn.commit()
        return int(getattr(cursor, "rowcount", 0) or 0)

    async def retry(
        self,
        item: QueueItem,
        reason: str,
        delay_seconds: int,
        result: Optional[dict[str, Any]] = None,
    ) -> None:
        now = get_local_now()
        available_at = (now + timedelta(seconds=max(0, delay_seconds))).isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'retrying',
                available_at = ?,
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = ?,
                updated_at = ?
            WHERE action_id = ?
            """,
            (available_at, reason[:1000], now.isoformat(), item.action["action_id"]),
        )
        await self._finish_attempt(item, "retrying", result or {}, reason)
        await conn.commit()

    async def dead_letter(
        self,
        item: QueueItem,
        reason: str,
        result: Optional[dict[str, Any]] = None,
    ) -> None:
        now = get_local_now().isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            INSERT INTO erp_dead_letters (
                dead_letter_id, action_id, reason, payload_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (
                f"dead-{uuid.uuid4().hex}",
                item.action["action_id"],
                reason[:1000],
                json.dumps(item.action.get("payload") or {}, ensure_ascii=False),
                now,
            ),
        )
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'failed',
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = ?,
                updated_at = ?
            WHERE action_id = ?
            """,
            (reason[:1000], now, item.action["action_id"]),
        )
        await self._finish_attempt(item, "failed", result or {}, reason)
        await conn.commit()

    async def wait_for_approval(self, item: QueueItem, reason: str) -> None:
        now = get_local_now().isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'waiting_approval',
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = ?,
                updated_at = ?
            WHERE action_id = ?
            """,
            (reason[:1000], now, item.action["action_id"]),
        )
        await self._finish_attempt(item, "waiting_approval", {}, reason)
        await conn.commit()

    async def complete(
        self,
        item: QueueItem,
        result: Optional[dict[str, Any]] = None,
    ) -> None:
        await self.repo.mark_action_completed(item.action["action_id"])
        now = get_local_now().isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_actions
            SET lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
            WHERE action_id = ?
            """,
            (now, item.action["action_id"]),
        )
        await self._finish_attempt(item, "completed", result or {}, None)
        await conn.commit()

    async def _finish_attempt(
        self,
        item: QueueItem,
        status: str,
        result: dict[str, Any],
        error: Optional[str],
    ) -> None:
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_action_attempts
            SET status = ?, result_json = ?, error = ?, finished_at = ?
            WHERE attempt_id = ?
            """,
            (
                status,
                json.dumps(result or {}, ensure_ascii=False, default=str),
                error[:1000] if error else None,
                get_local_now().isoformat(),
                item.attempt_id,
            ),
        )
