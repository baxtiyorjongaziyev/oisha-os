"""
Facade for Telegram Phone Enricher.
Delegates to modular subpackage in src.services.core.telegram.phone_enricher.
"""
from src.services.core.telegram.phone_enricher import (
    ENRICHMENT_TAG,
    NO_PHONE_TAG,
    PHONE_RE,
    TME_RE,
    USERNAME_RE,
    EnrichmentReport,
    EnrichmentResult,
    TelegramPhoneEnricher,
    extract_existing_phones,
    extract_usernames,
    normalize_phone,
    report_to_dict,
)

__all__ = [
    "ENRICHMENT_TAG",
    "NO_PHONE_TAG",
    "PHONE_RE",
    "TME_RE",
    "USERNAME_RE",
    "EnrichmentReport",
    "EnrichmentResult",
    "TelegramPhoneEnricher",
    "extract_existing_phones",
    "extract_usernames",
    "normalize_phone",
    "report_to_dict",
]
