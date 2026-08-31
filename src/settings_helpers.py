"""
Settings normalization and validation helpers.
"""
from __future__ import annotations

from typing import Any, Dict, List


def normalize_telegram_chat_id(value: Any) -> Any:
    """Convert raw supergroup/channel IDs to Telegram's canonical -100... form."""
    if value in (None, ""):
        return value
    try:
        chat_id = int(value)
    except (TypeError, ValueError):
        return value
    digits = str(abs(chat_id))
    if chat_id >= 0 or digits.startswith("100") or len(digits) < 10:
        return chat_id
    return -int(f"100{digits}")


OPTIONAL_ENV_KEYS = {
    "ADMIN_BOT_TOKEN",
    "TELEGRAM_MCP_SESSION_STRING",
    "TELEGRAM_WEBHOOK_SECRET",
    "AIOGRAM_WEBHOOK_BASE_URL",
    "TELEGRAM_MINI_APP_URL",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_AI_API_TOKEN",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
    "NVIDIA_NIM_API_KEY",
    "TOGETHERAI_API_KEY",
    "VAPI_API_KEY",
    "VAPI_PHONE_NUMBER_ID",
    "HUGGINGFACE_API_KEY",
    "CEREBRAS_API_KEY",
    "MISTRAL_API_KEY",
    "SAMBANOVA_API_KEY",
    "AMOCRM_CLIENT_SECRET",
    "AIRTABLE_API_KEY",
    "AIRTABLE_BASE_ID",
    "AIRTABLE_OAUTH_CLIENT_ID",
    "AIRTABLE_OAUTH_CLIENT_SECRET",
    "AIRTABLE_ACCESS_TOKEN",
    "AIRTABLE_REFRESH_TOKEN",
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
    "AMOCRM_TG_CHAT_FIELD_ID",
    "CRM_GROUP_ID",
    "PROJECTS_GROUP_ID",
    "TEAM_GROUP_ID",
    "TASKS_GROUP_ID",
    "STAGNATION_GROUP_ID",
    "WOW_SERVICE_GROUP_ID",
    "HISOBCHI_FINANCE_GROUP_ID",
    "HISOBCHI_KIRIM_TOPIC_ID",
    "HISOBCHI_CHIQIM_TOPIC_ID",
    "HISOBCHI_PNL_TOPIC_ID",
    "HISOBCHI_CASHFLOW_TOPIC_ID",
    "HISOBCHI_BALANCE_TOPIC_ID",
    "CRM_TOPIC_ID",
    "PROJECTS_TOPIC_ID",
    "TOPIC_CRM_ID",
    "TOPIC_REPORTS_ID",
    "TOPIC_TASKS_ID",
    "TOPIC_MEETINGS_ID",
    "TOPIC_SELLER_1_LEADS_ID",
    "TOPIC_SELLER_2_LEADS_ID",
    "TOPIC_FOLLOWUP_ID",
    "TOPIC_GENERAL_ID",
    "TOPIC_KIRIM_ID",
    "STAGNATION_TOPIC_ID",
    "WOW_SERVICE_TOPIC_ID",
    "GSHEET_ID",
    "HISOBCHI_GSHEET_ID",
    "HISOBCHI_GSHEET_CREDS_FILE",
    "HISOBCHI_QARZDORLIK_TOPIC_ID",
    "HISOBCHI_PNL_WORKSHEET_GID",
    "GDRIVE_OFFLOAD_FOLDER_ID",
    "AMOCRM_CRON_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "CMS_WEBHOOK_URL",
    "META_VERIFY_TOKEN",
    "META_PAGE_ACCESS_TOKEN",
    "META_APP_SECRET",
    "META_INSTAGRAM_USER_ID",
    "META_INSTAGRAM_ACCOUNT_ID",
    "INSTAGRAM_REPORT_AIRTABLE_TABLE",
    "GA4_PROPERTY_ID",
    "GA4_CREDENTIALS_JSON",
    "SANITY_PROJECT_ID",
    "SANITY_DATASET",
    "SANITY_TOKEN",
}

CHAT_ID_ENV_KEYS = (
    "CRM_GROUP_ID",
    "PROJECTS_GROUP_ID",
    "TEAM_GROUP_ID",
    "TASKS_GROUP_ID",
    "STAGNATION_GROUP_ID",
    "WOW_SERVICE_GROUP_ID",
    "HISOBCHI_FINANCE_GROUP_ID",
    "TN6_GROUP_ID",
    "TN5_GROUP_ID",
    "TN4_GROUP_ID",
    "TN3_GROUP_ID",
    "TN2_GROUP_ID",
)


def normalize_empty_env_values(data: Any) -> Any:
    """Normalize whitespace and strip empty string overrides."""
    if not isinstance(data, dict):
        return data
    for key, value in list(data.items()):
        if isinstance(value, str):
            data[key] = value.lstrip("\ufeff").strip()
        elif hasattr(value, "get_secret_value"):
            data[key] = value.get_secret_value().lstrip("\ufeff").strip()

    for key in OPTIONAL_ENV_KEYS:
        if data.get(key) == "":
            data[key] = None
    for key in CHAT_ID_ENV_KEYS:
        data[key] = normalize_telegram_chat_id(data.get(key))
    return data
