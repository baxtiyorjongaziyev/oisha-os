"""
Registry builder for tool adapters.
"""
from __future__ import annotations

from typing import Any, Optional

from src.services.core.airtable_sync import AirtableSync
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.tool_adapters_pkg.airtable import AirtableProjectAdapter
from src.services.core.tool_adapters_pkg.amocrm import AmoCRMLeadAdapter
from src.services.core.tool_adapters_pkg.telegram import TelegramNotificationAdapter
from src.services.core.tool_registry import ToolRegistry


def build_default_tool_registry(
    bot_token: Optional[str] = None,
    amocrm: Optional[AmoCRMSync] = None,
    airtable: Optional[AirtableSync] = None,
    bot: Optional[Any] = None,
    db: Optional[Any] = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    if bot_token:
        registry.register(TelegramNotificationAdapter(bot_token))
    if amocrm:
        registry.register(AmoCRMLeadAdapter(amocrm))
    if airtable:
        registry.register(AirtableProjectAdapter(airtable))
    return registry
