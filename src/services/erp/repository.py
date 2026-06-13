from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from src.services.erp.models import ERPAction, ERPEvent, ERPWorkflow, VerificationResult
from src.services.erp.schema import initialize_erp_schema
from src.time_utils import get_local_now


WORKFLOW_TRANSITIONS = {
    "new": {"planned", "blocked", "failed"},
    "planned": {"waiting_approval", "ready", "blocked", "failed"},
    "waiting_approval": {"ready", "blocked", "failed"},
    "ready": {"executing", "blocked", "failed"},
    "executing": {"verifying", "retrying", "failed"},
    "verifying": {"completed", "retrying", "failed"},
    "retrying": {"ready", "executing", "blocked", "failed"},
    "blocked": {"ready", "failed"},
    "completed": set(),
    "failed": {"retrying"},
}

ERP_TABLES = {
    "erp_events",
    "erp_identities",
    "erp_identity_links",
    "erp_workflows",
    "erp_workflow_steps",
    "erp_actions",
    "erp_action_attempts",
    "erp_verifications",
    "erp_approvals",
    "erp_dead_letters",
    "erp_metric_snapshots",
}


def _json(value: Dict[str, Any]) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


class ERPRepository:
    def __init__(self, db: Any):
        self.db = db

    async def initialize(self) -> None:
        conn = await self.db.get_connection()
        await initialize_erp_schema(conn)
        await conn.commit()

    async def record_event(self, event: ERPEvent) -> bool:
        if await self._exists("erp_events", "raw_hash", event.raw_hash):
            return False
        conn = await self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO erp_events (
                event_id, event_type, source, entity_type, entity_id,
                occurred_at, correlation_id, payload_json, raw_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.source,
                event.entity_type,
                event.entity_id,
                event.occurred_at,
                event.correlation_id,
                _json(event.payload),
                event.raw_hash,
                get_local_now().isoformat(),
            ),
        )
        await conn.commit()
        return True

    async def create_workflow(self, workflow: ERPWorkflow) -> bool:
        if workflow.status not in WORKFLOW_TRANSITIONS:
            raise ValueError(f"unknown_workflow_status:{workflow.status}")
        if await self._exists("erp_workflows", "workflow_id", workflow.workflow_id):
            return False
        now = get_local_now().isoformat()
        conn = await self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO erp_workflows (
                workflow_id, workflow_type, entity_type, entity_id,
                correlation_id, status, data_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow.workflow_id,
                workflow.workflow_type,
                workflow.entity_type,
                workflow.entity_id,
                workflow.correlation_id,
                workflow.status,
                _json(workflow.data),
                now,
                now,
            ),
        )
        await conn.commit()
        return True

    async def transition_workflow(self, workflow_id: str, new_status: str) -> bool:
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"workflow_not_found:{workflow_id}")
        current = str(workflow["status"])
        if new_status not in WORKFLOW_TRANSITIONS:
            raise ValueError(f"unknown_workflow_status:{new_status}")
        if new_status not in WORKFLOW_TRANSITIONS[current]:
            raise ValueError(f"illegal_workflow_transition:{current}->{new_status}")
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE erp_workflows SET status = ?, updated_at = ? WHERE workflow_id = ?",
            (new_status, get_local_now().isoformat(), workflow_id),
        )
        await conn.commit()
        return True

    async def create_action(self, action: ERPAction) -> bool:
        if await self._exists("erp_actions", "idempotency_key", action.idempotency_key):
            return False
        if not await self._exists("erp_workflows", "workflow_id", action.workflow_id):
            raise ValueError(f"workflow_not_found:{action.workflow_id}")
        now = get_local_now().isoformat()
        conn = await self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO erp_actions (
                action_id, workflow_id, action_type, target, payload_json,
                risk_level, idempotency_key, expected_result_json,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                action.action_id,
                action.workflow_id,
                action.action_type,
                action.target,
                _json(action.payload),
                action.risk_level,
                action.idempotency_key,
                _json(action.expected_result),
                now,
                now,
            ),
        )
        await conn.commit()
        return True

    async def record_verification(
        self,
        action_id: str,
        result: VerificationResult,
    ) -> str:
        if not await self._exists("erp_actions", "action_id", action_id):
            raise ValueError(f"action_not_found:{action_id}")
        verification_id = f"verify-{uuid.uuid4().hex}"
        conn = await self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO erp_verifications (
                verification_id, action_id, success, source,
                expected_json, actual_json, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verification_id,
                action_id,
                bool(result.success),
                result.source,
                _json(result.expected),
                _json(result.actual),
                result.reason,
                get_local_now().isoformat(),
            ),
        )
        await conn.commit()
        return verification_id

    async def mark_action_completed(self, action_id: str) -> bool:
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT COUNT(*) FROM erp_verifications WHERE action_id = ? AND success = 1",
            (action_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row or int(row[0] or 0) < 1:
            raise ValueError(f"successful_verification_required:{action_id}")
        await conn.execute(
            "UPDATE erp_actions SET status = 'completed', updated_at = ? WHERE action_id = ?",
            (get_local_now().isoformat(), action_id),
        )
        await conn.commit()
        return True

    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        conn = await self.db.get_connection()
        async with conn.execute(
            """
            SELECT workflow_id, workflow_type, entity_type, entity_id,
                   correlation_id, status, data_json, created_at, updated_at
            FROM erp_workflows WHERE workflow_id = ?
            """,
            (workflow_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return {
            "workflow_id": row[0],
            "workflow_type": row[1],
            "entity_type": row[2],
            "entity_id": row[3],
            "correlation_id": row[4],
            "status": row[5],
            "data": json.loads(row[6] or "{}"),
            "created_at": row[7],
            "updated_at": row[8],
        }

    async def get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        conn = await self.db.get_connection()
        async with conn.execute(
            """
            SELECT action_id, workflow_id, action_type, target, payload_json,
                   risk_level, idempotency_key, expected_result_json,
                   status, created_at, updated_at
            FROM erp_actions WHERE action_id = ?
            """,
            (action_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return {
            "action_id": row[0],
            "workflow_id": row[1],
            "action_type": row[2],
            "target": row[3],
            "payload": json.loads(row[4] or "{}"),
            "risk_level": row[5],
            "idempotency_key": row[6],
            "expected_result": json.loads(row[7] or "{}"),
            "status": row[8],
            "created_at": row[9],
            "updated_at": row[10],
        }

    async def count_rows(self, table: str) -> int:
        if table not in ERP_TABLES:
            raise ValueError(f"unknown_erp_table:{table}")
        conn = await self.db.get_connection()
        async with conn.execute(f"SELECT COUNT(*) FROM {table}") as cursor:  # nosec B608
            row = await cursor.fetchone()
        return int(row[0] or 0) if row else 0

    async def _exists(self, table: str, column: str, value: str) -> bool:
        allowed = {
            ("erp_events", "raw_hash"),
            ("erp_workflows", "workflow_id"),
            ("erp_actions", "action_id"),
            ("erp_actions", "idempotency_key"),
        }
        if (table, column) not in allowed:
            raise ValueError(f"unsupported_lookup:{table}.{column}")
        conn = await self.db.get_connection()
        query = f"SELECT 1 FROM {table} WHERE {column} = ? LIMIT 1"  # nosec B608
        async with conn.execute(query, (value,)) as cursor:
            return await cursor.fetchone() is not None
