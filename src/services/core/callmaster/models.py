"""
Callmaster data models and utility helpers.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

DATA_FILE_ENV = "CALLMASTER_STATE_FILE"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_phone(raw: str) -> str:
    """Normalize Uzbekistan-friendly phone numbers to +998XXXXXXXXX."""
    digits = re.sub(r"\D+", "", raw or "")
    if not digits:
        raise ValueError("phone_required")
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+998{digits[1:]}"
    if raw.strip().startswith("+") and 10 <= len(digits) <= 15:
        return f"+{digits}"
    raise ValueError("invalid_phone")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class Campaign:
    id: str
    name: str
    audio_url: str
    status: str = "draft"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    description: str = ""
    max_parallel_calls: int = 10
    retry_limit: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Contact:
    id: str
    campaign_id: str
    phone: str
    name: str = ""
    lead_id: Optional[int] = None
    status: str = "pending"
    attempts_count: int = 0
    last_event: str = ""
    last_digit: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallAttempt:
    id: str
    campaign_id: str
    contact_id: str
    phone: str
    provider: str = "local"
    provider_call_id: str = ""
    status: str = "queued"
    digit: str = ""
    duration_sec: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)
