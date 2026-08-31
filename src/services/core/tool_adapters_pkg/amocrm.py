"""
AmoCRM lead tool adapter.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.tool_registry import ToolResult

logger = logging.getLogger(__name__)


class AmoCRMLeadAdapter:
    tool_name = "amocrm_leads"

    def __init__(self, amocrm: AmoCRMSync):
        self.amocrm = amocrm
        self._user_cache: Dict[int, str] = {}

    async def fetch_leads(self, limit: int = 100) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self.amocrm.get_leads, limit)
        except Exception as exc:
            logger.error("[AMOCRM TOOL] fetch_leads failed: %s", exc)
            return []

    async def fetch_stagnated_leads(self, hours: int = 24) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, self.amocrm.check_stagnated_leads, hours
            )
        except Exception as exc:
            logger.error("[AMOCRM TOOL] fetch_stagnated_leads failed: %s", exc)
            return []

    async def get_user_name(self, user_id: int) -> str:
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        loop = asyncio.get_event_loop()
        try:
            name = await loop.run_in_executor(
                None, self.amocrm.get_user_name, user_id
            )
            self._user_cache[user_id] = name or f"User {user_id}"
            return self._user_cache[user_id]
        except Exception as exc:
            logger.warning("[AMOCRM TOOL] get_user_name failed: %s", exc)
            return f"User {user_id}"

    def get_last_error(self) -> Optional[str]:
        return getattr(self.amocrm, "last_error", None)

    async def create_followup_task(
        self,
        lead_id: int,
        text: str,
        complete_till: int,
        responsible_user_id: Optional[int] = None,
    ) -> ToolResult:
        result = await self.amocrm.create_task(
            int(lead_id),
            text,
            int(complete_till),
            responsible_user_id=responsible_user_id,
        )
        task_id = self._extract_embedded_id(result, "tasks")
        success = bool(result and task_id)
        reason = None if success else (self.get_last_error() or "task_create_failed")
        blocked = reason in {
            "lead_closed_for_tasks",
            "lead_state_unavailable_for_tasks",
        }
        return ToolResult(
            tool_name="amocrm.followup_task",
            success=success,
            status="ok" if success else ("blocked" if blocked else "failed"),
            reason=reason,
            metadata={
                "lead_id": int(lead_id),
                "task_id": task_id,
                "complete_till": int(complete_till),
                "responsible_user_id": responsible_user_id,
            },
        )

    async def add_lead_note(self, lead_id: int, text: str) -> ToolResult:
        result = await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), text)
        note_id = self._extract_embedded_id(result, "notes")
        success = bool(result and note_id)
        return ToolResult(
            tool_name="amocrm.lead_note",
            success=success,
            status="ok" if success else "failed",
            reason=None if success else (self.get_last_error() or "note_create_failed"),
            metadata={"lead_id": int(lead_id), "note_id": note_id},
        )

    @staticmethod
    def _extract_embedded_id(result: Any, collection_name: str) -> Optional[int]:
        if not isinstance(result, dict):
            return None
        embedded = result.get("_embedded") or {}
        collection = embedded.get(collection_name) or []
        if isinstance(collection, list) and collection:
            item = collection[0] or {}
            if isinstance(item, dict) and item.get("id"):
                return int(item["id"])
        return None
