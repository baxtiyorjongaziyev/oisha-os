"""
Facade for Telegram SalesCoach Store.
Delegates to modular subpackage in src.services.core.salescoach_store.
"""
from src.services.core.salescoach_store import (
    ConversationAnalysisRecord,
    TaskWriteAudit,
    TelegramSalesCoachStore,
    _decode_analysis_row,
    _maybe_await,
    _now_iso,
    _privacy_safe_analysis,
    _privacy_safe_value,
    _row_to_dict,
)

__all__ = [
    "ConversationAnalysisRecord",
    "TaskWriteAudit",
    "TelegramSalesCoachStore",
    "_decode_analysis_row",
    "_maybe_await",
    "_now_iso",
    "_privacy_safe_analysis",
    "_privacy_safe_value",
    "_row_to_dict",
]
