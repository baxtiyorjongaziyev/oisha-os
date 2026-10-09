"""crm_automation_audit jadvali + kill-switch (CrmActionExecutor uchun store)."""

import json
import time
from typing import Any, Dict, Optional

from src.services.core.salescoach_store.models import _maybe_await

KILL_SWITCH_KEY = "crm_automation:enabled"
_ENABLED_VALUES = {"1", "true", "yes", "on", "enabled"}


class DbCrmAutomationStore:
    def __init__(self, db: Any):
        self.db = db

    async def _query(self, sql: str, params: tuple = ()) -> Any:
        connection = await _maybe_await(self.db.get_connection())
        cursor = await _maybe_await(connection.execute(sql, params))
        commit = getattr(connection, "commit", None)
        if callable(commit):
            await _maybe_await(commit())
        return cursor

    async def initialize(self) -> None:
        await self._query(
            """
            CREATE TABLE IF NOT EXISTS crm_automation_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                success INTEGER NOT NULL DEFAULT 0,
                dry_run INTEGER NOT NULL DEFAULT 0,
                rolled_back INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        await self._query(
            "CREATE INDEX IF NOT EXISTS idx_crm_auto_lead_time "
            "ON crm_automation_audit(lead_id, created_at)"
        )

    async def is_enabled(self) -> bool:
        # Fail-safe: kalit yo'q bo'lsa o'chiq.
        raw = await _maybe_await(self.db.get_state(KILL_SWITCH_KEY, "false"))
        return str(raw or "").strip().lower() in _ENABLED_VALUES

    async def count_recent(self, lead_id: int, window_seconds: int) -> int:
        cursor = await self._query(
            "SELECT COUNT(*) FROM crm_automation_audit "
            "WHERE lead_id = ? AND created_at >= ? AND dry_run = 0 AND success = 1",
            (int(lead_id), int(time.time()) - int(window_seconds)),
        )
        row = await _maybe_await(cursor.fetchone())
        return int(row[0]) if row else 0

    async def record(self, entry: Dict[str, Any]) -> int:
        cursor = await self._query(
            "INSERT INTO crm_automation_audit "
            "(lead_id, action, before_json, after_json, success, dry_run, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                int(entry["lead_id"]),
                str(entry["action"]),
                json.dumps(entry.get("before") or {}, ensure_ascii=False),
                json.dumps(entry.get("after") or {}, ensure_ascii=False),
                1 if entry.get("success") else 0,
                1 if entry.get("dry_run") else 0,
                int(entry.get("created_at") or time.time()),
            ),
        )
        return int(getattr(cursor, "lastrowid", 0) or 0)

    async def get(self, audit_id: int) -> Optional[Dict[str, Any]]:
        cursor = await self._query(
            "SELECT id, lead_id, action, before_json, after_json, success, dry_run, rolled_back "
            "FROM crm_automation_audit WHERE id = ?",
            (int(audit_id),),
        )
        row = await _maybe_await(cursor.fetchone())
        if not row:
            return None
        return {
            "id": row[0],
            "lead_id": row[1],
            "action": row[2],
            "before": json.loads(row[3] or "{}"),
            "after": json.loads(row[4] or "{}"),
            "success": bool(row[5]),
            "dry_run": bool(row[6]),
            "rolled_back": bool(row[7]),
        }

    async def mark_rolled_back(self, audit_id: int) -> None:
        await self._query(
            "UPDATE crm_automation_audit SET rolled_back = 1 WHERE id = ?", (int(audit_id),)
        )
