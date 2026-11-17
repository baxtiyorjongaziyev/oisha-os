"""Shared task registry: one owner per task, atomic claim, evidence on close.

Oisha, Amina va Mr.Jon uchun yagona vazifalar reyestri. Har bir vazifaning
bitta egasi bor, faqat egasi uni oladi (claim) va faqat dalil bilan yopadi.
Storage is injected as an async ``execute(query, params) -> rows`` callable so
production uses ``database_pool`` and tests use in-memory SQLite.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

Executor = Callable[[str, Optional[List[Any]]], Awaitable[List[Any]]]

KNOWN_BOTS = frozenset({"oisha", "amina", "mrjon"})
STATUSES = frozenset({"open", "in_progress", "done", "failed", "cancelled"})

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS bot_tasks ("
    " id TEXT PRIMARY KEY,"
    " idempotency_key TEXT UNIQUE,"
    " title TEXT NOT NULL,"
    " domain TEXT NOT NULL DEFAULT 'general',"
    " owner TEXT NOT NULL,"
    " created_by TEXT NOT NULL,"
    " status TEXT NOT NULL DEFAULT 'open',"
    " payload TEXT NOT NULL DEFAULT '{}',"
    " evidence TEXT,"
    " error TEXT,"
    " due_at TEXT,"
    " created_at TEXT NOT NULL,"
    " updated_at TEXT NOT NULL)"
)
INDEX = "CREATE INDEX IF NOT EXISTS idx_bot_tasks_owner_status ON bot_tasks(owner, status)"


class TaskRegistryError(ValueError):
    """Invalid input or a transition the caller is not allowed to make."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_bot(name: str, field: str) -> str:
    bot = (name or "").strip().lower()
    if bot not in KNOWN_BOTS:
        raise TaskRegistryError(f"unknown_{field}:{name}")
    return bot


def _row_to_dict(row: Any) -> Dict[str, Any]:
    data = dict(row)
    for key in ("payload", "evidence"):
        raw = data.get(key)
        if isinstance(raw, str) and raw:
            try:
                data[key] = json.loads(raw)
            except ValueError:
                pass
    return data


class TaskRegistry:
    def __init__(self, execute: Executor):
        self._execute = execute
        self._ready = False

    async def ensure_schema(self) -> None:
        if self._ready:
            return
        await self._execute(SCHEMA, [])
        await self._execute(INDEX, [])
        self._ready = True

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        await self.ensure_schema()
        rows = await self._execute("SELECT * FROM bot_tasks WHERE id = ?", [task_id])
        return _row_to_dict(rows[0]) if rows else None

    async def create(
        self,
        *,
        title: str,
        owner: str,
        created_by: str,
        domain: str = "general",
        payload: Optional[Dict[str, Any]] = None,
        due_at: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a task. Same ``idempotency_key`` returns the existing task."""
        await self.ensure_schema()
        title = (title or "").strip()
        if not title:
            raise TaskRegistryError("empty_title")
        owner = _check_bot(owner, "owner")
        created_by = _check_bot(created_by, "creator")
        if idempotency_key:
            rows = await self._execute(
                "SELECT * FROM bot_tasks WHERE idempotency_key = ?", [idempotency_key]
            )
            if rows:
                return _row_to_dict(rows[0])
        task_id = uuid.uuid4().hex
        now = _now()
        await self._execute(
            "INSERT OR IGNORE INTO bot_tasks (id, idempotency_key, title, domain, owner,"
            " created_by, status, payload, due_at, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)",
            [task_id, idempotency_key, title, domain, owner, created_by,
             json.dumps(payload or {}, ensure_ascii=False), due_at, now, now],
        )
        if idempotency_key:
            rows = await self._execute(
                "SELECT * FROM bot_tasks WHERE idempotency_key = ?", [idempotency_key]
            )
            return _row_to_dict(rows[0])
        return await self.get(task_id)  # type: ignore[return-value]

    async def list(
        self, *, owner: Optional[str] = None, status: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        await self.ensure_schema()
        clauses, params = [], []
        if owner:
            clauses.append("owner = ?")
            params.append(_check_bot(owner, "owner"))
        if status:
            if status not in STATUSES:
                raise TaskRegistryError(f"unknown_status:{status}")
            clauses.append("status = ?")
            params.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 200)))
        rows = await self._execute(
            f"SELECT * FROM bot_tasks{where} ORDER BY created_at DESC LIMIT ?",  # nosec B608
            params,
        )
        return [_row_to_dict(r) for r in rows]

    async def _transition(
        self, task_id: str, bot: str, from_status: str, to_status: str, extra: Dict[str, Any]
    ) -> Dict[str, Any]:
        bot = _check_bot(bot, "bot")
        before = await self.get(task_id)
        if before is None:
            raise TaskRegistryError("task_not_found")
        if before["owner"] != bot:
            raise TaskRegistryError(f"not_owner:{before['owner']}")
        if before["status"] != from_status:
            raise TaskRegistryError(f"bad_state:{before['status']}")
        sets = ["status = ?", "updated_at = ?"] + [f"{k} = ?" for k in extra]
        params: List[Any] = [to_status, _now(), *extra.values(), task_id, bot, from_status]
        # Conditional UPDATE is the atomic guard: only the owner, only from the
        # expected state. Read-back below verifies who won.
        await self._execute(
            f"UPDATE bot_tasks SET {', '.join(sets)}"  # nosec B608
            " WHERE id = ? AND owner = ? AND status = ?",
            params,
        )
        task = await self.get(task_id)
        if task is None:
            raise TaskRegistryError("task_not_found")
        if task["owner"] != bot:
            raise TaskRegistryError(f"not_owner:{task['owner']}")
        if task["status"] != to_status:
            raise TaskRegistryError(f"bad_state:{task['status']}")
        return task

    async def claim(self, task_id: str, bot: str) -> Dict[str, Any]:
        return await self._transition(task_id, bot, "open", "in_progress", {})

    async def complete(self, task_id: str, bot: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Close as done. Evidence is required: no proof, no 'done'."""
        if not evidence:
            raise TaskRegistryError("evidence_required")
        return await self._transition(
            task_id, bot, "in_progress", "done",
            {"evidence": json.dumps(evidence, ensure_ascii=False)},
        )

    async def fail(self, task_id: str, bot: str, error: str) -> Dict[str, Any]:
        if not (error or "").strip():
            raise TaskRegistryError("error_required")
        return await self._transition(
            task_id, bot, "in_progress", "failed", {"error": error.strip()[:2000]}
        )

    async def reassign(self, task_id: str, bot: str, new_owner: str) -> Dict[str, Any]:
        """Owner hands an open task to the bot that owns that domain."""
        bot = _check_bot(bot, "bot")
        new_owner = _check_bot(new_owner, "owner")
        before = await self.get(task_id)
        if before is None:
            raise TaskRegistryError("task_not_found")
        if before["owner"] != bot:
            raise TaskRegistryError(f"not_owner:{before['owner']}")
        if before["status"] != "open":
            raise TaskRegistryError(f"bad_state:{before['status']}")
        await self._execute(
            "UPDATE bot_tasks SET owner = ?, updated_at = ?"
            " WHERE id = ? AND owner = ? AND status = 'open'",
            [new_owner, _now(), task_id, bot],
        )
        task = await self.get(task_id)
        if task is None or task["owner"] != new_owner:
            raise TaskRegistryError("reassign_lost_race")
        return task
