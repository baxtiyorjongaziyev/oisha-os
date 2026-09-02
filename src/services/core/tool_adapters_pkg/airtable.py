"""
Airtable projects tool adapter.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.services.core.airtable_sync import AirtableSync

logger = logging.getLogger(__name__)


class AirtableProjectAdapter:
    tool_name = "airtable_projects"

    def __init__(self, airtable: Optional[AirtableSync] = None):
        self.airtable = airtable or AirtableSync()

    async def fetch_projects(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, self.airtable.get_projects, force_refresh
            )
        except Exception as exc:
            logger.error("[AIRTABLE TOOL] fetch_projects failed: %s", exc)
            return []

    async def fetch_upcoming_deadlines(self, hours: int = 24) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, self.airtable.get_upcoming_deadlines, hours
            )
        except Exception as exc:
            logger.error("[AIRTABLE TOOL] fetch_upcoming_deadlines failed: %s", exc)
            return []
