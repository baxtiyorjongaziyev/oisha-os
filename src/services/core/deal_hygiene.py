"""
Facade for Deal Hygiene.
Delegates to modular subpackage in src.services.core.hygiene.
"""
from src.services.core.hygiene import (
    AmoCRMDealHygieneAgent,
    DealHygieneFinding,
    DealSignal,
    DuplicateDealFinding,
    HARD_NOISE_KEYWORDS,
    METASELL_LOST_OUTCOMES,
    SYSTEM_TAGS,
    LeadIdentity,
    extract_phones,
    extract_usernames,
    normalize_phone,
)

__all__ = [
    "AmoCRMDealHygieneAgent",
    "DealHygieneFinding",
    "DealSignal",
    "DuplicateDealFinding",
    "HARD_NOISE_KEYWORDS",
    "METASELL_LOST_OUTCOMES",
    "SYSTEM_TAGS",
    "LeadIdentity",
    "extract_phones",
    "extract_usernames",
    "normalize_phone",
]
