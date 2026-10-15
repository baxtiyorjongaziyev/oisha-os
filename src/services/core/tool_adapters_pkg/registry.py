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
        tg_adapter = TelegramNotificationAdapter(bot_token)
        registry.register(tg_adapter.tool_name, tg_adapter)
    if amocrm:
        crm_adapter = AmoCRMLeadAdapter(amocrm)
        registry.register(crm_adapter.tool_name, crm_adapter)
    if airtable:
        at_adapter = AirtableProjectAdapter(airtable)
        registry.register(at_adapter.tool_name, at_adapter)
    return registry
