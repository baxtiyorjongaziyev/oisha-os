"""
Facade for Telegram AI Features.
Delegates to modular subpackage in src.services.core.telegram.ai_features.
"""
from src.services.core.telegram.ai_features import (
    BOT_API_10_ALLOWED_UPDATES,
    BotApiTransport,
    BotApiUpdateHandler,
    GuestMessageContext,
    TelegramAIFeature,
    TelegramBotAPI10Client,
    TelegramBotAPIError,
    TelegramBotAPILongPoller,
    build_input_rich_message,
    build_live_feature_status,
    build_offline_feature_status,
    build_text_article_result,
    classify_update,
    clean_payload,
    extract_guest_message_context,
    feature_matrix_payload,
    rich_paragraph,
    rich_section_heading,
)

__all__ = [
    "BOT_API_10_ALLOWED_UPDATES",
    "BotApiTransport",
    "BotApiUpdateHandler",
    "TelegramAIFeature",
    "GuestMessageContext",
    "TelegramBotAPIError",
    "feature_matrix_payload",
    "clean_payload",
    "build_text_article_result",
    "build_input_rich_message",
    "rich_paragraph",
    "rich_section_heading",
    "extract_guest_message_context",
    "classify_update",
    "build_offline_feature_status",
    "build_live_feature_status",
    "TelegramBotAPI10Client",
    "TelegramBotAPILongPoller",
]
