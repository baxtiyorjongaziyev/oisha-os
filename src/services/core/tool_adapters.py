"""
Facade for Tool Adapters.
Delegates to modular subpackage in src.services.core.tool_adapters_pkg.
"""
from src.services.core.tool_adapters_pkg.telegram import (
    TelegramNotificationAdapter,
    configure_userbot_group_fallback,
    send_group_message_with_fallback,
)
from src.services.core.tool_adapters_pkg.amocrm import AmoCRMLeadAdapter
from src.services.core.tool_adapters_pkg.airtable import AirtableProjectAdapter
from src.services.core.tool_adapters_pkg.registry import build_default_tool_registry

__all__ = [
    "TelegramNotificationAdapter",
    "configure_userbot_group_fallback",
    "send_group_message_with_fallback",
    "AmoCRMLeadAdapter",
    "AirtableProjectAdapter",
    "build_default_tool_registry",
]
