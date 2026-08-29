"""
Facade for Telegram SalesCoach Runtime.
Delegates to modular subpackage in src.services.core.salescoach_runtime.
"""
from src.services.core.salescoach_runtime import (
    AmoCRMConversationMatcher,
    AmoCRMTaskAdapter,
    TelegramSalesCoachNotifier,
    TelethonConversationLoader,
    _env_bool,
    _env_int,
    _internal_user_ids,
    _maybe_await,
    _parse_id_list,
    _personal_sender_checker,
    handle_salescoach_callback,
    install_telegram_salescoach,
)

__all__ = [
    "TelethonConversationLoader",
    "AmoCRMConversationMatcher",
    "AmoCRMTaskAdapter",
    "TelegramSalesCoachNotifier",
    "handle_salescoach_callback",
    "install_telegram_salescoach",
    "_env_bool",
    "_env_int",
    "_internal_user_ids",
    "_maybe_await",
    "_parse_id_list",
    "_personal_sender_checker",
]
