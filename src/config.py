from src.settings import settings


def _secret_or_none(secret):
    if not secret:
        return None
    return secret.get_secret_value()


def __getattr__(name: str):
    if name == "BOT_TOKEN":
        return settings.BOT_TOKEN.get_secret_value()
    if name == "GEMINI_API_KEY":
        return settings.GEMINI_API_KEY.get_secret_value()
    if name == "API_ID":
        return settings.API_ID
    if name == "API_HASH":
        return settings.API_HASH
    if name == "AMOCRM_SUBDOMAIN":
        return settings.AMOCRM_SUBDOMAIN
    if name == "AMOCRM_CLIENT_ID":
        return settings.AMOCRM_CLIENT_ID
    if name == "AMOCRM_CLIENT_SECRET":
        return _secret_or_none(settings.AMOCRM_CLIENT_SECRET)
    if name == "AMOCRM_REDIRECT_URL":
        return settings.AMOCRM_REDIRECT_URL
    if name == "AIRTABLE_API_KEY":
        return _secret_or_none(settings.AIRTABLE_API_KEY)
    if name == "AIRTABLE_BASE_ID":
        return settings.AIRTABLE_BASE_ID
    if name == "CRM_GROUP_ID":
        return settings.CRM_GROUP_ID
    if name == "PROJECTS_GROUP_ID":
        return settings.PROJECTS_GROUP_ID or settings.CRM_GROUP_ID
    if name == "CRM_TOPIC_ID":
        return settings.CRM_TOPIC_ID
    if name == "TOPIC_CRM_ID":
        return settings.TOPIC_CRM_ID
    if name == "TOPIC_REPORTS_ID":
        return settings.TOPIC_REPORTS_ID
    if name == "TOPIC_TASKS_ID":
        return settings.TOPIC_TASKS_ID
    if name == "TOPIC_GENERAL_ID":
        return settings.TOPIC_GENERAL_ID
    if name == "TOPIC_KIRIM_ID":
        return settings.TOPIC_KIRIM_ID
    if name == "GSHEET_ID":
        return settings.GSHEET_ID
    if name == "GSHEET_CREDS_FILE":
        return settings.GSHEET_CREDS_FILE
    if name == "OWNER_ID":
        return settings.OWNER_ID
    if name == "WHITELIST_IDS":
        return settings.WHITELIST_IDS
    if name == "SYSTEM_INSTRUCTION":
        return settings.SYSTEM_INSTRUCTION + "\n\n[AGENTIC OPS] Suhbat davomida aniq topshiriqlar berilsa yoki kelishilsa, avtomatik ravishda [TASK: title=...|assigned_to=...|deadline=...] formatida javob oxirida vazifa yarating."
    raise AttributeError(name)


__all__ = [
    "BOT_TOKEN",
    "GEMINI_API_KEY",
    "API_ID",
    "API_HASH",
    "AMOCRM_SUBDOMAIN",
    "AMOCRM_CLIENT_ID",
    "AMOCRM_CLIENT_SECRET",
    "AMOCRM_REDIRECT_URL",
    "AIRTABLE_API_KEY",
    "AIRTABLE_BASE_ID",
    "CRM_GROUP_ID",
    "PROJECTS_GROUP_ID",
    "CRM_TOPIC_ID",
    "TOPIC_CRM_ID",
    "TOPIC_REPORTS_ID",
    "TOPIC_TASKS_ID",
    "TOPIC_GENERAL_ID",
    "TOPIC_KIRIM_ID",
    "GSHEET_ID",
    "GSHEET_CREDS_FILE",
    "OWNER_ID",
    "WHITELIST_IDS",
    "SYSTEM_INSTRUCTION",
]
