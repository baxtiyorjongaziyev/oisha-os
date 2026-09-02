"""
Data models and helper functions for Telegram phone enrichment.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

USERNAME_RE = re.compile(r"(?<![A-Za-z0-9_])@?([A-Za-z][A-Za-z0-9_]{4,31})")
TME_RE = re.compile(r"t\.me/(?:joinchat/)?([A-Za-z0-9_]{5,32})", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\d{2}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")

ENRICHMENT_TAG = "OISHA_PHONE_ENRICHED"
NO_PHONE_TAG = "OISHA_PHONE_MISSING"


@dataclass
class EnrichmentResult:
    contact_id: int
    contact_name: str
    found_username: Optional[str] = None
    resolved_phone: Optional[str] = None
    telegram_user_id: Optional[int] = None
    status: str = "skipped"  # found | not_found | hidden | error | applied | dry_run | skipped
    reason: str = ""
    evidence: List[str] = field(default_factory=list)


@dataclass
class EnrichmentReport:
    generated_at: str
    checked: int = 0
    no_phone: int = 0
    resolved: int = 0
    applied: int = 0
    hidden: int = 0
    errors: int = 0
    dry_run: bool = True
    results: List[EnrichmentResult] = field(default_factory=list)


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    if len(digits) > 12:
        digits = digits[-12:]
    if len(digits) >= 9 and not digits.startswith("998") and len(digits) == 9:
        digits = "998" + digits
    return digits


def extract_usernames(text: str) -> Set[str]:
    text = text or ""
    found: Set[str] = set()
    for match in TME_RE.finditer(text):
        found.add(match.group(1).lower())
    for match in USERNAME_RE.finditer(text):
        token = match.group(1).lower()
        if 5 <= len(token) <= 32 and not token.isdigit():
            found.add(token)
    # filter obviously non-usernames
    blacklist = {"gmail", "outlook", "yandex", "mail", "ru", "uz", "com"}
    return {u for u in found if u not in blacklist}


def extract_existing_phones(contact: Dict[str, Any]) -> Set[str]:
    phones: Set[str] = set()
    for field in contact.get("custom_fields_values") or []:
        if field.get("field_code") != "PHONE":
            continue
        for value in field.get("values") or []:
            normalized = normalize_phone(value.get("value"))
            if normalized:
                phones.add(normalized)
    return phones


def report_to_dict(report: EnrichmentReport) -> Dict[str, Any]:
    return {
        "generated_at": report.generated_at,
        "checked": report.checked,
        "no_phone": report.no_phone,
        "resolved": report.resolved,
        "applied": report.applied,
        "hidden": report.hidden,
        "errors": report.errors,
        "dry_run": report.dry_run,
        "results": [asdict(r) for r in report.results],
    }
