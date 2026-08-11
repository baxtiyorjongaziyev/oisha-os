"""Owner-approved policy for automatic customer-facing messages."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


_JUMA_TEMPLATES = (
    "Juma muborak bo'lsin. Bugungi kuningiz xayrli, ishlaringiz unumli o'tsin.",
    "Juma ayyomingiz muborak. Oilangizga tinchlik, ishlaringizga baraka tilayman.",
    "Juma muborak. Ko'nglingiz xotirjam, kuningiz fayzli o'tsin.",
    "Juma ayyomi muborak bo'lsin. Yaxshi niyatlaringiz amalga oshsin.",
    "Juma muborak bo'lsin. Bugun sizga sokinlik, fayz va yaxshi xabarlar tilayman.",
    "Juma ayyomingiz muborak. Mehnatingizga unum, xonadoningizga baraka tilayman.",
    "Juma muborak. Kuningiz mazmunli va yaqinlaringiz davrasida fayzli o'tsin.",
    "Juma ayyomi muborak bo'lsin. Sog'lik, xotirjamlik va halol rizq tilayman.",
)


def automatic_customer_send_allowed(kind: str, *, now: datetime | None = None) -> bool:
    """Allow only the explicit Friday-greeting exception."""
    current = now or datetime.now()
    return kind.strip().lower() == "juma" and current.weekday() == 4


def build_humanized_juma_greeting(name: Any, now: datetime | None = None) -> str:
    """Build a short conversational greeting that rotates every ISO week."""
    current = now or datetime.now()
    clean_name = re.sub(r"\s+", " ", str(name or "")).strip(" ,.!-")
    clean_name = clean_name or "aziz inson"
    _, week, _ = current.isocalendar()
    body = _JUMA_TEMPLATES[(week - 1) % len(_JUMA_TEMPLATES)]
    return f"Assalomu alaykum, {clean_name}. {body}"
