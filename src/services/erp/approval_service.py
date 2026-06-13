from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.services.erp.repository import ERPRepository
from src.time_utils import get_local_now


@dataclass(frozen=True)
class Approval:
    approval_id: str
    action_id: str
    status: str
    requested_from: str
    decided_by: str
    reason: str
    expires_at: str
    created_at: str
    decided_at: str


class ApprovalService:
    def __init__(self, repo: ERPRepository):
        self.repo = repo

    async def request(
        self,
        *,
        action_id: str,
        requested_from: str,
        reason: str,
        ttl_seconds: int = 900,
    ) -> Approval:
        if not await self.repo.get_action(action_id):
            raise ValueError(f"action_not_found:{action_id}")
        existing = await self.get_for_action(action_id)
        if existing and existing.status == "pending":
            return existing

        now = get_local_now()
        approval_id = f"approval-{uuid.uuid4().hex}"
        expires_at = (now + timedelta(seconds=max(1, ttl_seconds))).isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            INSERT INTO erp_approvals (
                approval_id, action_id, status, requested_from, decided_by,
                reason, expires_at, created_at, decided_at
            ) VALUES (?, ?, 'pending', ?, NULL, ?, ?, ?, NULL)
            """,
            (
                approval_id,
                action_id,
                requested_from,
                reason,
                expires_at,
                now.isoformat(),
            ),
        )
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'waiting_approval', updated_at = ?
            WHERE action_id = ?
            """,
            (now.isoformat(), action_id),
        )
        await conn.commit()
        approval = await self.get(approval_id)
        if approval is None:
            raise RuntimeError("approval_write_failed")
        return approval

    async def approve(self, approval_id: str, *, decided_by: str) -> Approval:
        approval = await self.get(approval_id)
        if approval is None:
            raise ValueError(f"approval_not_found:{approval_id}")
        if approval.status == "expired":
            raise ValueError(f"approval_expired:{approval_id}")
        if approval.status != "pending":
            raise ValueError(f"approval_not_pending:{approval.status}")

        now = get_local_now().isoformat()
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_approvals
            SET status = 'approved', decided_by = ?, decided_at = ?
            WHERE approval_id = ? AND status = 'pending'
            """,
            (decided_by, now, approval_id),
        )
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'pending', available_at = ?, updated_at = ?
            WHERE action_id = ?
            """,
            (now, now, approval.action_id),
        )
        await conn.commit()
        return await self._required(approval_id)

    async def reject(
        self,
        approval_id: str,
        *,
        decided_by: str,
        reason: str = "",
    ) -> Approval:
        approval = await self.get(approval_id)
        if approval is None:
            raise ValueError(f"approval_not_found:{approval_id}")
        if approval.status == "expired":
            raise ValueError(f"approval_expired:{approval_id}")
        if approval.status != "pending":
            raise ValueError(f"approval_not_pending:{approval.status}")

        now = get_local_now().isoformat()
        final_reason = reason or approval.reason
        conn = await self.repo.db.get_connection()
        await conn.execute(
            """
            UPDATE erp_approvals
            SET status = 'rejected', decided_by = ?, reason = ?, decided_at = ?
            WHERE approval_id = ? AND status = 'pending'
            """,
            (decided_by, final_reason, now, approval_id),
        )
        await conn.execute(
            """
            UPDATE erp_actions
            SET status = 'failed', last_error = 'approval_rejected', updated_at = ?
            WHERE action_id = ?
            """,
            (now, approval.action_id),
        )
        await conn.commit()
        return await self._required(approval_id)

    async def is_approved(self, action_id: str) -> bool:
        approval = await self.get_for_action(action_id)
        return bool(approval and approval.status == "approved")

    async def get_for_action(self, action_id: str) -> Optional[Approval]:
        conn = await self.repo.db.get_connection()
        async with conn.execute(
            """
            SELECT approval_id
            FROM erp_approvals
            WHERE action_id = ?
            ORDER BY created_at DESC, approval_id DESC
            LIMIT 1
            """,
            (action_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return await self.get(str(row[0]))

    async def get(self, approval_id: str) -> Optional[Approval]:
        conn = await self.repo.db.get_connection()
        async with conn.execute(
            """
            SELECT approval_id, action_id, status, requested_from, decided_by,
                   reason, expires_at, created_at, decided_at
            FROM erp_approvals
            WHERE approval_id = ?
            """,
            (approval_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None

        approval = self._from_row(row)
        if approval.status == "pending" and self._is_expired(approval.expires_at):
            now = get_local_now().isoformat()
            await conn.execute(
                """
                UPDATE erp_approvals
                SET status = 'expired', decided_at = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (now, approval_id),
            )
            await conn.execute(
                """
                UPDATE erp_actions
                SET status = 'failed', last_error = 'approval_expired', updated_at = ?
                WHERE action_id = ?
                """,
                (now, approval.action_id),
            )
            await conn.commit()
            async with conn.execute(
                """
                SELECT approval_id, action_id, status, requested_from, decided_by,
                       reason, expires_at, created_at, decided_at
                FROM erp_approvals WHERE approval_id = ?
                """,
                (approval_id,),
            ) as cursor:
                row = await cursor.fetchone()
            return self._from_row(row)
        return approval

    async def _required(self, approval_id: str) -> Approval:
        approval = await self.get(approval_id)
        if approval is None:
            raise RuntimeError(f"approval_missing_after_update:{approval_id}")
        return approval

    @staticmethod
    def _is_expired(value: str) -> bool:
        if not value:
            return True
        expires_at = datetime.fromisoformat(value)
        return expires_at <= get_local_now()

    @staticmethod
    def _from_row(row) -> Approval:
        return Approval(
            approval_id=str(row[0]),
            action_id=str(row[1]),
            status=str(row[2]),
            requested_from=str(row[3] or ""),
            decided_by=str(row[4] or ""),
            reason=str(row[5] or ""),
            expires_at=str(row[6] or ""),
            created_at=str(row[7] or ""),
            decided_at=str(row[8] or ""),
        )
