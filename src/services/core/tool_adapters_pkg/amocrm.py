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

    async def create_followup_task(
        self,
        lead_id: int,
        text: str,
        complete_till: int,
        responsible_user_id: Optional[int] = None,
    ) -> ToolResult:
        loop = asyncio.get_event_loop()
        try:
            res = await loop.run_in_executor(
                None,
                self.amocrm.add_task,
                lead_id,
                text,
                complete_till,
                responsible_user_id,
            )
            return ToolResult(
                tool_name="amocrm.create_task",
                success=bool(res),
                metadata={"lead_id": lead_id, "task_id": res},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="amocrm.create_task",
                success=False,
                reason=str(exc),
                metadata={"lead_id": lead_id},
            )

    async def add_lead_note(self, lead_id: int, text: str) -> ToolResult:
        loop = asyncio.get_event_loop()
        try:
            res = await loop.run_in_executor(
                None, self.amocrm.add_lead_note, lead_id, text
            )
            return ToolResult(
                tool_name="amocrm.add_note",
                success=bool(res),
                metadata={"lead_id": lead_id},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="amocrm.add_note",
                success=False,
                reason=str(exc),
                metadata={"lead_id": lead_id},
            )
