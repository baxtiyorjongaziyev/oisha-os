"""
Data models, date/time parsers, and candidate extraction heuristics for meeting scheduler.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Optional
from zoneinfo import ZoneInfo
import structlog

logger = structlog.get_logger()

TZ = ZoneInfo("Asia/Tashkent")

MEETING_TERMS = (
    "uchrashuv",
    "suhbat",
    "intervyu",
    "konsultatsiya",
    "zoom",
    "google meet",
    "ofis",
    "kelolasiz",
    "kelasiz",
    "kelaman",
    "keladi",
)

CONFIRMATION_TERMS = (
    "yozib qo'ydim",
    "yozib quydim",
    "belgiladim",
    "calendar",
    "kalendar",
    "ok",
    "hop",
    "bo'ladi",
    "boladi",
    "kelaman",
    "tasdiq",
)

LOCATION_HINTS = ("ofis", "manzil", "geopozitsiya", "геопозиция", "maps.google")
LEAD_TERMS = (
    "branding",
    "brending",
    "logo",
    "logotip",
    "naming",
    "nomlash",
    "brandbook",
    "brendbuk",
    "qadoq",
    "dizayn",
    "patent",
    "narx",
    "tijoriy taklif",
    "brief",
    "brif",
    "loyiha",
    "xizmat",
    "konsultatsiya",
)


@dataclass
class ContextMessage:
    text: str
    is_outgoing: bool
    sender_name: str = ""
    created_at: Optional[datetime] = None


@dataclass
class MeetingCandidate:
    summary: str
    start_time: datetime
    end_time: datetime
    description: str
    location: str = ""
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_explicit_date(text: str, reference: datetime) -> Optional[datetime]:
    date_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text)
    if date_match:
        day, month, year = map(int, date_match.groups())
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day, tzinfo=TZ)
        except ValueError:
            return None

    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        try:
            return datetime(year, month, day, tzinfo=TZ)
        except ValueError:
            return None

    lowered = text.lower()
    if "indinga" in lowered:
        return (reference + timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if "ertaga" in lowered:
        return (reference + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if "bugun" in lowered:
        return reference.replace(hour=0, minute=0, second=0, microsecond=0)
    return None


def _parse_time(text: str) -> Optional[tuple[int, int]]:
    lowered = text.lower()
    candidates = [
        r"\bsoat\s+(\d{1,2})[:.\s](\d{2})\b",
        r"\b(\d{1,2}):(\d{2})\b",
        r"(?<![./-])\b(\d{1,2})\.(\d{2})\b(?![./-]\d)",
        r"\b(\d{1,2})\s+(\d{2})\b",
        r"\bsoat\s+(\d{1,2})\b",
    ]
    for pattern in candidates:
        match = re.search(pattern, lowered)
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2)) if len(match.groups()) > 1 else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    return None


def _extract_location(messages: Iterable[ContextMessage]) -> str:
    location_parts: List[str] = []
    for msg in messages:
        text = msg.text or ""
        lowered = text.lower()
        if any(hint in lowered for hint in LOCATION_HINTS):
            location_parts.append(_clean_text(text))
        maps_match = re.search(r"https?://\S*maps\.google\S+", text)
        if maps_match:
            location_parts.append(maps_match.group(0))
        coord_match = re.search(r"q=(-?\d+\.\d+),(-?\d+\.\d+)", text)
        if coord_match:
            location_parts.append(f"{coord_match.group(1)},{coord_match.group(2)}")
    return "\n".join(dict.fromkeys(location_parts))[:500]


def extract_meeting_candidate(
    messages: List[ContextMessage],
    reference: Optional[datetime] = None,
    participant_name: str = "Mijoz",
) -> Optional[MeetingCandidate]:
    """Extract a concrete meeting from recent chat context."""
    if not messages:
        return None

    reference = (reference or datetime.now(TZ)).astimezone(TZ)
    ordered = [msg for msg in messages if _clean_text(msg.text)]
    if not ordered:
        return None

    combined = "\n".join(msg.text for msg in ordered)
    lowered = combined.lower()
    if not any(term in lowered for term in MEETING_TERMS):
        return None

    date_base: Optional[datetime] = None
    date_evidence = ""
    for msg in ordered:
        parsed_date = _parse_explicit_date(msg.text, msg.created_at or reference)
        if parsed_date:
            date_base = parsed_date
            date_evidence = msg.text

    time_value: Optional[tuple[int, int]] = None
    time_evidence = ""
    for msg in ordered:
        parsed_time = _parse_time(msg.text)
        if parsed_time:
            time_value = parsed_time
            time_evidence = msg.text

    if not date_base or not time_value:
        return None

    has_confirmation = any(term in lowered for term in CONFIRMATION_TERMS)
    has_owner_question = any(
        msg.is_outgoing and ("kelolasiz" in msg.text.lower() or "nech" in msg.text.lower())
        for msg in ordered
    )
    has_client_time_reply = any(
        (not msg.is_outgoing) and _parse_time(msg.text) for msg in ordered
    )
    if not (has_confirmation or (has_owner_question and has_client_time_reply)):
        return None

    hour, minute = time_value
    start = date_base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start < reference - timedelta(hours=2):
        return None
    end = start + timedelta(hours=1)

    location = _extract_location(ordered)
    evidence = [
        f"Sana: {_clean_text(date_evidence)}",
        f"Vaqt: {_clean_text(time_evidence)}",
    ]
    if location:
        evidence.append("Manzil: Telegram kontekstdan olindi")

    return MeetingCandidate(
        summary=f"Suhbat: {participant_name}",
        start_time=start,
        end_time=end,
        location=location,
        description=(
            "Oisha Telegram suhbatidan avtomatik yaratdi.\n\n"
            + "\n".join(f"{'Baxtiyorjon' if m.is_outgoing else participant_name}: {m.text}" for m in ordered[-8:])
        )[:2000],
        confidence=0.9 if has_confirmation else 0.82,
        evidence=evidence,
    )
