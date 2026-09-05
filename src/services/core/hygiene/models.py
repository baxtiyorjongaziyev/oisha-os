"""
Data models, signal weights, and pattern helpers for deal hygiene.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set

logger = logging.getLogger("AmoCRMDealHygiene")


PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
USERNAME_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_]{5,32})")

HARD_NOISE_KEYWORDS = {
    "spam": "Spam yoki bot xabar",
    "reklama": "Begona reklama",
    "noto'g'ri raqam": "Noto'g'ri raqam",
    "notogri raqam": "Noto'g'ri raqam",
    "wrong number": "Noto'g'ri raqam",
    "qiziqmagan": "Mijoz qiziqmagan",
    "qiziqmaydi": "Mijoz qiziqmagan",
    "mijoz emas": "Mijoz emas",
    "not client": "Mijoz emas",
    "shaxsiy": "Shaxsiy yozishma",
    "oila": "Shaxsiy/oila aloqasi",
    "qarindosh": "Shaxsiy/oila aloqasi",
}

METASELL_LOST_OUTCOMES = {
    "lost",
    "no_interest",
    "not_interested",
    "wrong_number",
    "spam",
    "invalid",
}

SYSTEM_TAGS = {
    "personal": "OISHA_PERSONAL_NOT_CLIENT",
    "spam": "OISHA_SPAM_OR_WRONG",
    "low_quality_lost": "OISHA_LOW_QUALITY_LOST",
    "needs_review": "OISHA_NEEDS_REVIEW",
    "duplicate": "OISHA_DUPLICATE_SUSPECT",
}


@dataclass
class DealSignal:
    source: str
    message: str
    weight: float = 0.1


@dataclass
class DealHygieneFinding:
    lead_id: int
    lead_name: str
    category: str
    confidence: float
    reason: str
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = "review"
    amo_url: Optional[str] = None
    tag: str = SYSTEM_TAGS["needs_review"]


@dataclass
class DuplicateDealFinding:
    probability: float
    reason: str
    lead_ids: List[int]
    lead_names: List[str]
    phones: List[str] = field(default_factory=list)
    telegram_usernames: List[str] = field(default_factory=list)
    telegram_user_ids: List[int] = field(default_factory=list)
    contact_ids: List[int] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    recommended_action: str = "Birlashtirishdan oldin mas'ul bilan tekshiring"
    tag: str = SYSTEM_TAGS["duplicate"]


@dataclass
class LeadIdentity:
    lead_id: int
    lead_name: str
    status_id: Optional[int]
    pipeline_id: Optional[int]
    responsible_user_id: Optional[int]
    updated_at: Optional[int]
    phones: Set[str] = field(default_factory=set)
    telegram_usernames: Set[str] = field(default_factory=set)
    telegram_user_ids: Set[int] = field(default_factory=set)
    contact_ids: Set[int] = field(default_factory=set)
    note_text: str = ""


def normalize_phone(value: Any) -> str:
    """Return a stable Uzbek-friendly phone key."""
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    if len(digits) >= 9:
        return digits[-9:]
    return digits


def extract_phones(text: str) -> Set[str]:
    phones: Set[str] = set()
    for match in PHONE_RE.findall(text or ""):
        normalized = normalize_phone(match)
        if len(normalized) >= 9:
            phones.add(normalized)
    return phones


def extract_usernames(text: str) -> Set[str]:
    return {m.group(1).lower() for m in USERNAME_RE.finditer(text or "")}


def _safe_ts(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
