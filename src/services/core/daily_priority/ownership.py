"""Fail-closed attribution of a shared-login amoCRM deal to a real seller.

Never use amoCRM responsible_user_id: all sellers share that account.
Only an exact 'Sotuvchi' custom-field value or a verified seller tag counts.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any


# The October 2026 CRM setup plan calls this field "Menejer"; older setups
# and operator instructions may use "Sotuvchi". Both must match exactly.
SELLER_FIELD_NAMES = frozenset({"menejer", "sotuvchi", "seller"})
# Verified against src/services/core/crm/team_roster.py. No partial names.
SELLER_ALIASES = {
    "shahnoza": frozenset({"shaxnoza", "shahnoza abdijabborova"}),
    "rayxona": frozenset({"rayxon", "rayhona", "rayxona rahimova"}),
    "mumtozmaxal": frozenset({"mumtoz", "mumtozmahal", "mumtozmaxal normurodova"}),
}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _match(value: object, sellers: list[dict[str, Any]]) -> str | None:
    candidate = _norm(value)
    if not candidate:
        return None
    matched = {
        str(seller.get("key"))
        for seller in sellers
        if candidate in (
            {_norm(seller.get("key")), _norm(seller.get("name"))}
            | {_norm(alias) for alias in SELLER_ALIASES.get(str(seller.get("key")), ())}
        )
    }
    return next(iter(matched)) if len(matched) == 1 else None


def configured_seller_field_ids() -> frozenset[int]:
    """IDs must come from an actual read-only amoCRM metadata check."""
    values: set[int] = set()
    for token in os.getenv("DAILY_PRIORITY_SELLER_FIELD_IDS", "").split(","):
        token = token.strip()
        if token.isdecimal() and int(token) > 0:
            values.add(int(token))
    return frozenset(values)


def _field_values(lead: dict[str, Any]) -> list[str]:
    result: list[str] = []
    trusted_ids = configured_seller_field_ids()
    for field in lead.get("custom_fields_values") or []:
        if not isinstance(field, dict):
            continue
        name_verified = _norm(field.get("field_name")) in SELLER_FIELD_NAMES
        try:
            id_verified = int(field.get("field_id") or 0) in trusted_ids
        except (TypeError, ValueError):
            id_verified = False
        if not (name_verified or id_verified):
            continue
        for item in field.get("values") or []:
            value = item.get("value") if isinstance(item, dict) else item
            if value is not None and str(value).strip():
                result.append(str(value).strip())
    return result


def _tag_candidates(lead: dict[str, Any], sellers: list[dict[str, Any]]) -> set[str]:
    raw = (lead.get("_embedded") or {}).get("tags") or lead.get("tags") or []
    candidates: set[str] = set()
    for item in raw:
        name = item.get("name") if isinstance(item, dict) else item
        if not isinstance(name, str):
            continue
        tag = name.strip()
        # Tags with other meanings must never match a seller substring.
        match = re.fullmatch(r"(?:sotuvchi|seller)\s*[:=/]\s*(.+)", tag, flags=re.I)
        if match:
            tag = match.group(1).strip()
        key = _match(tag, sellers)
        if key:
            candidates.add(key)
    return candidates


def resolve_seller_key(lead: dict[str, Any], sellers: list[dict[str, Any]]) -> str | None:
    """Return one verified seller key; unknown or conflicting evidence -> None."""
    values = _field_values(lead)
    field_owner: str | None = None
    if values:
        owners = [_match(value, sellers) for value in values]
        # Unknown value must not be silently replaced with a matching tag.
        if None in owners or len(set(owners)) != 1:
            return None
        field_owner = owners[0]

    tag_owners = _tag_candidates(lead, sellers)
    if len(tag_owners) > 1:
        return None
    tag_owner = next(iter(tag_owners)) if tag_owners else None
    if field_owner and tag_owner and field_owner != tag_owner:
        return None
    return field_owner or tag_owner
