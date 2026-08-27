"""Owner-approved policy for automatic customer-facing messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any


_JUMA_TEMPLATES = (
    "Juma muborak bo‘lsin 🤲 Alloh xonadoningizga baraka, ishlaringizga rivoj bersin. Bugungi qilgan duolaringiz qabul bo‘lib, ko‘nglingiz doim xotirjam bo‘lsin.",
    "Juma muborak bo‘lsin! 🤲 Alloh kuningizni xayrli, ishlaringizni barakali qilsin. Yaxshi niyatlaringizga yetkazsin.",
    "Juma muborak bo‘lsin! 🤲 Alloh rizqingizga baraka bersin, ko‘nglingizni xotirjam qilsin. Niyat qilgan yaxshi ishlaringizga yetkazib, duolaringizni qabul qilsin.",
)


def automatic_customer_send_allowed(kind: str, *, now: datetime | None = None) -> bool:
    """Allow only the explicit Friday-greeting exception."""
    current = now or datetime.now()
    return kind.strip().lower() == "juma" and current.weekday() == 4


def build_humanized_juma_greeting(name: Any, now: datetime | None = None) -> str:
    """Build a name-free conversational greeting that rotates every ISO week."""
    current = now or datetime.now()
    _, week, _ = current.isocalendar()
    body = _JUMA_TEMPLATES[(week - 1) % len(_JUMA_TEMPLATES)]
    return f"Assalomu alaykum. {body}"
