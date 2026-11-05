from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

# Owner's identifiers
OWNER_USER_ID = 150074828

# Calendar proposal settings
try:
    LOCAL_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Tashkent"))
except Exception:  # pragma: no cover - tzdata yoʼq muhitlar uchun
    LOCAL_TZ = timezone(timedelta(hours=5))

DEFAULT_MEETING_DURATION = timedelta(hours=1)

_WEEKDAY_INDEX = {
    "dushanba": 0,
    "seshanba": 1,
    "chorshanba": 2,
    "payshanba": 3,
    "juma": 4,
    "shanba": 5,
    "yakshanba": 6,
}

_WEEKDAY_LABELS = {
    0: "dushanba",
    1: "seshanba",
    2: "chorshanba",
    3: "payshanba",
    4: "juma",
    5: "shanba",
    6: "yakshanba",
}

_MONTH_INDEX = {
    "yanvar": 1,
    "fevral": 2,
    "mart": 3,
    "aprel": 4,
    "may": 5,
    "iyun": 6,
    "iyul": 7,
    "avgust": 8,
    "sentabr": 9,
    "sentyabr": 9,
    "oktabr": 10,
    "oktyabr": 10,
    "noyabr": 11,
    "dekabr": 12,
}

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\b")
_TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2})\s*[-–]?\s*(" + "|".join(_MONTH_INDEX) + r")\b"
)

_MEETING_KEYWORDS = (
    "uchrashuv",
    "uchrashamiz",
    "uchrashamizmi",
    "uchrashdik",
    "koʼrishamiz",
    "korishamiz",
    "koʼrishdik",
    "kelishdik",
    "kelishamiz",
    "offline",
    "ofisda",
    "zoom",
    "meet",
    "sessiya",
    "qoʼngʼiroq",
    "qongiroq",
    "gaplashamiz",
    "gaplashdik",
    "kelaman",
    "keladi",
    "keladilar",
)

_APOSTROPHES = ("\u2018", "\u2019", "\u02bb", "\u02bc", "`", "\u00b4")


def _normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    for mark in _APOSTROPHES:
        lowered = lowered.replace(mark, "'")
    return lowered


# Kalit soʼzlar unicode apostrof bilan yozilgani uchun normalizatsiya qilinadi
_MEETING_KEYWORDS_NORMALIZED = tuple(_normalize_text(word) for word in _MEETING_KEYWORDS)


def _coerce_reference(reference: Optional[datetime]) -> datetime:
    if reference is None:
        return datetime.now(LOCAL_TZ)
    if reference.tzinfo is None:
        return reference.replace(tzinfo=LOCAL_TZ)
    return reference.astimezone(LOCAL_TZ)


def source_timestamp(value: Any) -> Optional[datetime]:
    """Parse the source timestamp; naive timestamps use the configured local zone."""
    if isinstance(value, datetime):
        return _coerce_reference(value)
    if isinstance(value, str):
        try:
            return _coerce_reference(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def is_canceled_meeting(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(k in normalized for k in _MEETING_KEYWORDS_NORMALIZED) and bool(
        re.search(r"\b(?:bekor|cancelled|canceled|отмен\w*)\b", normalized)
    )


def _explicit_date(day: int, month: int, year: Optional[str],
                   anchor: datetime) -> Optional[datetime]:
    target_year = int(year) if year else anchor.year
    if target_year < 100:
        target_year += 2000
    try:
        candidate = datetime(target_year, month, day, tzinfo=LOCAL_TZ)
        if not year and candidate.date() < anchor.date():
            candidate = candidate.replace(year=target_year + 1)
        return candidate
    except ValueError:
        return None


def _resolve_date(normalized: str, anchor: datetime) -> Optional[datetime]:
    numeric = _NUMERIC_DATE_RE.search(normalized)
    if numeric:
        return _explicit_date(int(numeric[1]), int(numeric[2]), numeric[3], anchor)
    text_date = _TEXT_DATE_RE.search(normalized)
    if text_date:
        return _explicit_date(int(text_date[1]), _MONTH_INDEX[text_date[2]], None, anchor)
    for word, days in (("indinga", 2), ("indin", 2), ("ertaga", 1), ("bugun", 0)):
        if re.search(rf"\b{word}\b", normalized):
            return anchor + timedelta(days=days)
    for name, index in _WEEKDAY_INDEX.items():
        if re.search(rf"\b{name}\b", normalized):
            return anchor + timedelta(days=(index - anchor.weekday()) % 7)
    return None


def _date_and_time(text: str):
    # Full dates and slash/hyphen dates cannot also supply a clock time.
    dates = list(_NUMERIC_DATE_RE.finditer(text))
    occupied = [m.span() for m in dates if m[3] or "." not in m[0]]
    for match in _TIME_RE.finditer(text):
        if any(match.start() < end and match.end() > start for start, end in occupied):
            continue
        # Dotted clocks require an explicit clock marker or a separate date.
        if "." in match[0] and not (
            re.search(r"\b(?:soat|bugun|ertaga|indin|indinga|" +
                      "|".join(_WEEKDAY_INDEX) + r")\b", text)
            or re.match(r"\s*(?:da|ga)\b", text[match.end():])
            or occupied or _TEXT_DATE_RE.search(text)
        ):
            continue
        date_text = text[:match.start()] + " " * len(match[0]) + text[match.end():]
        return date_text, match
    return text, None


def detect_calendar_appointment(
    text: str,
    reference: Optional[datetime] = None,
    *, source_dt: Optional[datetime] = None, require_source: bool = False,
) -> Optional[Dict[str, Any]]:
    """Uchrashuv kelishuvi (sana + vaqt) borligini aniqlaydi.

    Kalendar taklifini shakllantirish uchun yetarli maʼlumot boʼlsa dict qaytaradi,
    aks holda None.
    """
    if not text or len(text.strip()) < 3:
        return None

    normalized = _normalize_text(text)
    if is_canceled_meeting(text) or not any(keyword in normalized for keyword in _MEETING_KEYWORDS_NORMALIZED):
        return None

    date_text, time_match = _date_and_time(normalized)
    if not time_match:
        return None

    now = _coerce_reference(reference)
    if require_source and source_dt is None:
        return None
    anchor = _coerce_reference(source_dt) if source_dt is not None else now
    day = _resolve_date(date_text, anchor)
    if day is None:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ)

    if start <= now:
        return None

    end = start + DEFAULT_MEETING_DURATION
    return {
        "start": start,
        "end": end,
        "start_iso": start.isoformat(),
        "end_iso": end.isoformat(),
        "when_label": (
            f"{_WEEKDAY_LABELS[start.weekday()]}, "
            f"{start.strftime('%d.%m.%Y')} {start.strftime('%H:%M')}"
        ),
    }

