"""CrmActionPlanner rejasini AmoCRM'da bajarish: kill-switch, rate-limit, audit, rollback.

Mijozga xabar yubormaydi — faqat CRM ichki o'zgarishlari, shuning uchun quiet-hours
bu yerda bloklamaydi (Owner qarori, 2026-10-06).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence

from src.services.call_analytics.crm_actions import (
    CrmAction,
    FieldFillAction,
    FieldSuggestion,
    StageAction,
    TaskAction,
)

logger = logging.getLogger(__name__)

_TASK_DUE_SECONDS = 24 * 3600


class CrmAutomationStore(Protocol):
    async def is_enabled(self) -> bool: ...
    async def count_recent(self, lead_id: int, window_seconds: int) -> int: ...
    async def record(self, entry: Dict[str, Any]) -> int: ...
    async def get(self, audit_id: int) -> Optional[Dict[str, Any]]: ...
    async def mark_rolled_back(self, audit_id: int) -> None: ...


@dataclass
class ExecutionResult:
    audit_ids: List[int] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    skipped_reason: str = ""


class CrmActionExecutor:
    def __init__(
        self,
        amocrm: Any,
        store: CrmAutomationStore,
        *,
        dry_run: bool = False,
        max_changes_per_hour: int = 3,
        responsible_user_id: Optional[int] = None,
    ):
        self.amocrm = amocrm
        self.store = store
        self.dry_run = dry_run
        self.max_changes_per_hour = max_changes_per_hour
        self.responsible_user_id = responsible_user_id

    async def execute(self, lead_id: int, actions: Sequence[CrmAction]) -> ExecutionResult:
        result = ExecutionResult()
        result.suggestions = [
            f"{a.field_id}: {a.current} -> {a.proposed}" for a in actions if isinstance(a, FieldSuggestion)
        ]
        writes = [a for a in actions if not isinstance(a, FieldSuggestion)]
        if not writes:
            return result
        if not await self.store.is_enabled():
            result.skipped_reason = "disabled"
            return result
        if await self.store.count_recent(lead_id, 3600) >= self.max_changes_per_hour:
            result.skipped_reason = "rate_limited"
            logger.warning("[CRM AUTO] lead %s rate-limited", lead_id)
            return result

        for action in writes:
            success, before, after = await self._apply(lead_id, action)
            audit_id = await self.store.record(
                {
                    "lead_id": lead_id,
                    "action": type(action).__name__,
                    "before": before,
                    "after": after,
                    "success": success,
                    "dry_run": self.dry_run,
                    "created_at": int(time.time()),
                }
            )
            result.audit_ids.append(audit_id)
        return result

    async def _apply(self, lead_id: int, action: CrmAction) -> tuple:
        if isinstance(action, FieldFillAction):
            before, after = {"field_id": action.field_id, "value": ""}, {"field_id": action.field_id, "value": action.value}
            if self.dry_run:
                return True, before, after
            ok = await self.amocrm.update_lead_custom_fields(lead_id, {action.field_id: action.value})
            return bool(ok), before, after
        if isinstance(action, StageAction):
            before, after = {"status_id": action.from_status}, {"status_id": action.to_status}
            if self.dry_run:
                return True, before, after
            ok = await self.amocrm.update_lead_status(lead_id, action.to_status)
            return bool(ok), before, after
        if isinstance(action, TaskAction):
            after = {"text": action.text}
            if self.dry_run:
                return True, {}, after
            task = await self.amocrm.create_task(
                element_id=lead_id,
                text=action.text,
                complete_till=int(time.time()) + _TASK_DUE_SECONDS,
                responsible_user_id=self.responsible_user_id,
            )
            return bool(task), {}, after
        return False, {}, {}

    async def rollback(self, audit_id: int) -> bool:
        row = await self.store.get(audit_id)
        if not row or row.get("rolled_back") or not row.get("success") or row.get("dry_run"):
            return False
        lead_id, before = int(row["lead_id"]), row.get("before") or {}
        if row["action"] == "FieldFillAction":
            ok = await self.amocrm.update_lead_custom_fields(lead_id, {before["field_id"]: before.get("value", "")})
        elif row["action"] == "StageAction":
            ok = await self.amocrm.update_lead_status(lead_id, before["status_id"])
        else:
            return False  # task'ni menejer o'zi yopadi
        if ok:
            await self.store.mark_rolled_back(audit_id)
        return bool(ok)
