"""Thin compatibility shim over :mod:`src.settings`.

This module's ONLY responsibilities are:
  1. Unwrap ``SecretStr`` values into plain strings for legacy callers.
  2. Apply group/topic-id fallbacks (e.g. ``PROJECTS_GROUP_ID`` → ``CRM_GROUP_ID``).

It must NOT mutate or rewrite setting values — ``config.SYSTEM_INSTRUCTION`` is
guaranteed to equal ``settings.SYSTEM_INSTRUCTION``. Prefer importing
``src.settings.settings`` directly in new code.
"""
import os

from src.settings import settings

_MIN_SESSION_SECRET_BYTES = 32


def _secret_or_none(secret):
    if not secret:
        return None
    return getattr(secret, "get_secret_value", lambda: secret)()


def _session_secret() -> str:
    """Return a strong non-Telegram session key or fail closed."""
    secret = (
        os.environ.get("JWT_SECRET")
        or os.environ.get("OISHA_API_SECRET")
        or ""
    ).strip()
    if len(secret.encode("utf-8")) < _MIN_SESSION_SECRET_BYTES:
        raise RuntimeError(
            "JWT_SECRET or OISHA_API_SECRET must be at least 32 bytes for web sessions"
        )
    return secret


def __getattr__(name: str):
    if name == "BOT_TOKEN":
        return settings.BOT_TOKEN.get_secret_value()
    if name == "JWT_SECRET":
        return _session_secret()
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
        gid = settings.PROJECTS_GROUP_ID
        if not gid or (settings.CRM_GROUP_ID and gid == settings.CRM_GROUP_ID):
            return -1003114662117
        return gid
    if name == "PROJECTS_TOPIC_ID":
        tid = settings.PROJECTS_TOPIC_ID
        return 1 if tid is None else tid
    if name == "TASKS_GROUP_ID":
        return settings.TASKS_GROUP_ID or settings.PROJECTS_GROUP_ID or -1003114662117
    if name == "STAGNATION_GROUP_ID":
        return settings.STAGNATION_GROUP_ID or settings.CRM_GROUP_ID
    if name == "STAGNATION_TOPIC_ID":
        return (
            settings.STAGNATION_TOPIC_ID
            if settings.STAGNATION_TOPIC_ID is not None
            else settings.TOPIC_CRM_ID
        )
    if name == "WOW_SERVICE_GROUP_ID":
        gid = settings.WOW_SERVICE_GROUP_ID
        if not gid or (settings.CRM_GROUP_ID and gid == settings.CRM_GROUP_ID):
            return -1003114662117
        return gid
    if name == "WOW_SERVICE_TOPIC_ID":
        tid = settings.WOW_SERVICE_TOPIC_ID
        return 1 if tid is None else tid
    if name == "CRM_TOPIC_ID":
        return settings.CRM_TOPIC_ID
    if name == "TOPIC_CRM_ID":
        return settings.TOPIC_CRM_ID
    if name == "TOPIC_REPORTS_ID":
        return settings.TOPIC_REPORTS_ID
    if name == "TOPIC_TASKS_ID":
        return settings.TOPIC_TASKS_ID
    if name == "TOPIC_MEETINGS_ID":
        return settings.TOPIC_MEETINGS_ID
    if name == "TOPIC_SELLER_1_LEADS_ID":
        return settings.TOPIC_SELLER_1_LEADS_ID
    if name == "TOPIC_SELLER_2_LEADS_ID":
        return settings.TOPIC_SELLER_2_LEADS_ID
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
        # The [AGENTIC OPS] suffix now lives in settings.SYSTEM_INSTRUCTION itself,
        # so config.SYSTEM_INSTRUCTION and settings.SYSTEM_INSTRUCTION are identical.
        return settings.SYSTEM_INSTRUCTION
    if name == "META_VERIFY_TOKEN":
        return _secret_or_none(settings.META_VERIFY_TOKEN)
    if name == "META_PAGE_ACCESS_TOKEN":
        return _secret_or_none(settings.META_PAGE_ACCESS_TOKEN)
    if name == "META_APP_SECRET":
        return _secret_or_none(settings.META_APP_SECRET)
    raise AttributeError(name)


__all__ = [
    "BOT_TOKEN",
    "JWT_SECRET",
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
    "PROJECTS_TOPIC_ID",
    "TASKS_GROUP_ID",
    "STAGNATION_GROUP_ID",
    "STAGNATION_TOPIC_ID",
    "WOW_SERVICE_GROUP_ID",
    "WOW_SERVICE_TOPIC_ID",
    "CRM_TOPIC_ID",
    "TOPIC_CRM_ID",
    "TOPIC_REPORTS_ID",
    "TOPIC_TASKS_ID",
    "TOPIC_MEETINGS_ID",
    "TOPIC_SELLER_1_LEADS_ID",
    "TOPIC_SELLER_2_LEADS_ID",
    "TOPIC_GENERAL_ID",
    "TOPIC_KIRIM_ID",
    "GSHEET_ID",
    "GSHEET_CREDS_FILE",
    "OWNER_ID",
    "WHITELIST_IDS",
    "SYSTEM_INSTRUCTION",
    "META_VERIFY_TOKEN",
    "META_PAGE_ACCESS_TOKEN",
    "META_APP_SECRET",
]
