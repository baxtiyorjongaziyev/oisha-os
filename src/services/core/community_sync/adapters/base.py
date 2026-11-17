"""Adapterlar uchun umumiy yordamchilar."""

import re

from ..models import strip_suffix

NAME_PHONE = ("first_name", "last_name", "phone")


def split_name(full: str) -> tuple[str, str]:
    parts = strip_suffix(full).split(None, 1)
    return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")


def norm_phone(value: str) -> str:
    """E.164 shakli: faqat raqamlar; 9 xonali UZ raqamga 998 qöshiladi."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    return "+" + digits if len(digits) >= 10 else ""


def keys_of(changes) -> list[str]:
    seen: list[str] = []
    for c in changes:
        if c.key not in seen:
            seen.append(c.key)
    return seen


def result() -> dict:
    """keys: muvaffaqiyatli kalitlar; written: kalit -> haqiqatda yozilgan maydonlar."""
    return {"ok": 0, "failed": 0, "deferred": 0, "keys": [], "written": {}}
