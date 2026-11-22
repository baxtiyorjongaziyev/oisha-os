"""
Facade for Telegram AI Features (10–50 lines standard).
Delegates to modular subpackage in src.services.core.telegram.ai_features.
"""
from src.services.core.telegram.ai_features import (
    ALLOWED_BUTTON_STYLES, ALLOWED_FORUM_ICON_COLORS, BOT_API_10_ALLOWED_UPDATES,
    OISHA_PRIVATE_TOPICS, BotAPIExtensionsMixin, BotApiTransport, BotApiUpdateHandler,
    GuestMessageContext, TelegramAIFeature, TelegramBotAPI10Client, TelegramBotAPIError,
    TelegramBotAPILongPoller, bootstrap_owner_private_topics, build_bot_invite_link,
    build_date_time_entity, build_ephemeral_parameters, build_input_checklist,
    build_input_rich_message, build_live_feature_status, build_offline_feature_status,
    build_styled_inline_button, build_text_article_result, classify_update, clean_payload,
    consume_draft_stopped, enrich_lead_from_personal_channel, extract_checklist_tasks_done,
    extract_guest_message_context, extract_stopped_message_generation,
    extract_write_access_allowed_context, feature_matrix_payload,
    handle_botnews_service_update, mark_draft_stopped, rich_button_row,
    rich_expandable_blockquote, rich_paragraph, rich_section_heading, rich_table,
    send_client_native_checklist, send_oisha_kpi_report, sync_team_member_tags,
)

__all__ = [
    "ALLOWED_BUTTON_STYLES", "ALLOWED_FORUM_ICON_COLORS", "BOT_API_10_ALLOWED_UPDATES",
    "BotAPIExtensionsMixin", "BotApiTransport", "BotApiUpdateHandler", "OISHA_PRIVATE_TOPICS",
    "TelegramAIFeature", "GuestMessageContext", "TelegramBotAPIError",
    "feature_matrix_payload", "clean_payload", "build_bot_invite_link",
    "build_date_time_entity", "build_ephemeral_parameters", "build_input_checklist",
    "build_styled_inline_button", "build_text_article_result", "build_input_rich_message",
    "rich_button_row", "rich_expandable_blockquote", "rich_paragraph",
    "rich_section_heading", "rich_table", "extract_checklist_tasks_done",
    "extract_guest_message_context", "extract_stopped_message_generation",
    "extract_write_access_allowed_context", "classify_update",
    "build_offline_feature_status", "build_live_feature_status",
    "bootstrap_owner_private_topics", "consume_draft_stopped",
    "enrich_lead_from_personal_channel", "handle_botnews_service_update",
    "mark_draft_stopped", "send_client_native_checklist", "send_oisha_kpi_report",
    "sync_team_member_tags", "TelegramBotAPI10Client", "TelegramBotAPILongPoller",
]
