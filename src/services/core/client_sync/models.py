"""Canonical client profile model, eligibility filter, and non-destructive merger."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from src.services.core.crm.amocrm.phone_format import normalize_amocrm_phone

_COLD_NAME_RE = re.compile(
    r"^(?:автоконтакт|autocontact|звонок\s+на|mijoz|клиент|lead|лид|unknown|nomsiz|ismsiz|\+?\d[\d\s\-()]+)$",
    re.IGNORECASE,
)
_NOISE_TAGS = frozenset({"mycontacts", ""})


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_username(value: object) -> str:
    raw = clean_text(value).lstrip("@")
    if not raw or " " in raw:
        return ""
    return raw


def split_full_name(full_name: str) -> tuple[str, str]:
    cleaned = clean_text(full_name)
    if not cleaned:
        return "", ""
    parts = cleaned.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


@dataclass
class UnifiedClientProfile:
    """Single canonical client record shared across all 5 systems."""

    phone: str
    first_name: str = ""
    last_name: str = ""
    telegram_username: str = ""
    telegram_id: Optional[int] = None
    company: str = ""
    activity: str = ""
    region: str = ""
    stage: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)
    amocrm_contact_id: Optional[int] = None
    amocrm_lead_id: Optional[int] = None
    airtable_record_id: str = ""
    google_resource_name: str = ""
    notes: str = ""
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )

    def __post_init__(self) -> None:
        self.phone = normalize_amocrm_phone(self.phone)
        self.first_name = clean_text(self.first_name)
        self.last_name = clean_text(self.last_name)
        self.telegram_username = clean_username(self.telegram_username)
        self.company = clean_text(self.company)
        self.activity = clean_text(self.activity)
        self.region = clean_text(self.region)
        self.stage = clean_text(self.stage)
        self.source = clean_text(self.source)
        self.notes = str(self.notes or "").strip()
        self.tags = sorted({clean_text(t) for t in self.tags if clean_text(t).lower() not in _NOISE_TAGS})

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p).strip()

    @property
    def canonical_key(self) -> str:
        """Primary deduplication key: canonical +998XXXXXXXXX phone."""
        return self.phone


def is_eligible_client(profile: UnifiedClientProfile) -> bool:
    """Filter out cold/unnamed call spam so all 5 systems stay clean.

    Eligible when:
    - Has a valid canonical phone (starting with '+', >= 10 digits)
    - Has a real human/brand name (not 'Автоконтакт', 'Звонок на ...', 'Mijoz', or bare phone)
    """
    digits = re.sub(r"\D+", "", profile.phone)
    if not profile.phone.startswith("+") or len(digits) < 10:
        return False
    name = profile.full_name
    if len(name) < 2:
        return False
    if _COLD_NAME_RE.match(name):
        return False
    if name.lower().startswith(("автоконтакт ", "autocontact ", "звонок на ")):
        return False
    return True


def _pick_richer(current: str, incoming: str) -> str:
    cur, inc = clean_text(current), clean_text(incoming)
    if not cur:
        return inc
    if not inc:
        return cur
    return inc if len(inc) > len(cur) and _COLD_NAME_RE.match(cur) else cur


def merge_profiles(profiles: Iterable[UnifiedClientProfile]) -> UnifiedClientProfile:
    """Merge multiple partial records for the same client without losing data."""
    items = list(profiles)
    if not items:
        raise ValueError("merge_profiles requires at least one profile")

    base = UnifiedClientProfile(phone=items[0].phone)
    merged_tags: set[str] = set()
    note_chunks: list[str] = []

    for item in items:
        if not base.phone and item.phone:
            base.phone = item.phone
        base.first_name = _pick_richer(base.first_name, item.first_name)
        base.last_name = _pick_richer(base.last_name, item.last_name)
        base.telegram_username = base.telegram_username or item.telegram_username
        base.telegram_id = base.telegram_id or item.telegram_id
        base.company = _pick_richer(base.company, item.company)
        base.activity = _pick_richer(base.activity, item.activity)
        base.region = _pick_richer(base.region, item.region)
        base.stage = base.stage or item.stage
        base.source = base.source or item.source
        base.amocrm_contact_id = base.amocrm_contact_id or item.amocrm_contact_id
        base.amocrm_lead_id = base.amocrm_lead_id or item.amocrm_lead_id
        base.airtable_record_id = base.airtable_record_id or item.airtable_record_id
        base.google_resource_name = base.google_resource_name or item.google_resource_name
        merged_tags.update(item.tags)
        if item.notes and item.notes not in note_chunks:
            note_chunks.append(item.notes)

    base.tags = sorted(merged_tags)
    base.notes = "\n".join(note_chunks)
    return base
