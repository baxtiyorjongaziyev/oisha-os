"""
Facade for Telegram SalesCoach.
Delegates to modular subpackage in src.services.core.salescoach.
"""
from src.services.core.salescoach import (
    CrmMatch,
    TelegramConversationMessage,
    TelegramSalesCoach,
    _hash_value,
    _maybe_await,
    _normalize_message,
    _parse_datetime,
    conversation_fingerprint,
)

__all__ = [
    "CrmMatch",
    "TelegramConversationMessage",
    "TelegramSalesCoach",
    "_hash_value",
    "_maybe_await",
    "_normalize_message",
    "_parse_datetime",
    "conversation_fingerprint",
]
