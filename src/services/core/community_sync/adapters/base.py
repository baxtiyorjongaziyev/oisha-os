"""Adapterlar uchun umumiy yordamchilar."""

import re

from src.services.core.contact_intro_parser import normalize_phone

NAME_PHONE = ("first_name", "last_name", "phone")
_SUFFIX_RE = re.compile(r"\s*\b(?:TN|3K)\d+ Gr\s*$")


def strip_suffix(name: str) -> str:
    return _SUFFIX_RE.sub("", name or "").strip()


def split_name(full: str) -> tuple[str, str]:
    parts = strip_suffix(full).split(None, 1)
    return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")


def norm_phone(value: str) -> str:
    p = normalize_phone(value or "")
    return p if p.startswith("+998") and len(p) == 13 else ""


def keys_of(changes) -> list[str]:
    seen: list[str] = []
    for c in changes:
        if c.key not in seen:
            seen.append(c.key)
    return seen


def result() -> dict:
    return {"ok": 0, "failed": 0, "deferred": 0}
