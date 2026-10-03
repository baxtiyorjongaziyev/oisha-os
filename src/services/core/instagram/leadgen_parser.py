"""
Leadgen form field parsing and extraction utilities.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable

from src.services.core.instagram.leadgen_formatter import clean_form_key

NAME_KEYS = {
    "full_name", "name", "first_name", "last_name", "ismingizni_yozing",
    "ismingiz_nima", "ismingiz", "ism", "fio", "mijoz_ismi", "client_name", "your_name",
}
PHONE_KEYS = {
    "phone", "phone_number", "telefon", "tel", "mobile_phone",
    "telefon_raqamingizni_kiriting", "telefon_raqamingizni_yozing", "telefon_raqam",
    "telefon_raqamingiz", "telefon_raqamingz", "what_is_your_phone_number", "aloqa_uchun_telefon",
}
EMAIL_KEYS = {"email", "email_address", "e_mail", "pochta", "elektron_pochta"}


def _clean_key(value: str) -> str:
    return clean_form_key(value)


def _field_value(item: Dict[str, Any]) -> str:
    values = item.get("values")
    if isinstance(values, list):
        return ", ".join(str(v).strip() for v in values if str(v).strip())
    value = item.get("value")
    return str(value).strip() if value is not None else ""


def flatten_field_data(field_data: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """Convert Meta field_data[] into a simple key/value mapping."""
    fields: Dict[str, str] = {}
    for item in field_data or []:
        if not isinstance(item, dict):
            continue
        key = _clean_key(str(item.get("name") or ""))
        value = _field_value(item)
        if key and value:
            fields[key] = value
    return fields


def _is_name_field(key: str) -> bool:
    cleaned = _clean_key(key)
    if cleaned in NAME_KEYS:
        return True
    if any(w in cleaned for w in ("brend", "biznes", "brand", "company", "kompaniya", "nomi")):
        return False
    parts = cleaned.split("_")
    return "ism" in parts or "ismingiz" in parts or "fio" in parts or cleaned.startswith("ism")


def _is_phone_field(key: str) -> bool:
    cleaned = _clean_key(key)
    return cleaned in PHONE_KEYS or any(p in ("phone", "tel", "telefon") for p in cleaned.split("_"))


def _is_email_field(key: str) -> bool:
    cleaned = _clean_key(key)
    return cleaned in EMAIL_KEYS or any(p in ("email", "mail", "pochta") for p in cleaned.split("_"))


def _pick_name(fields: Dict[str, str]) -> str:
    for key in ("ismingizni_yozing", "ismingiz", "ism", "full_name", "name", "first_name", "fio", "client_name"):
        if fields.get(key) and fields[key].strip():
            return fields[key].strip()
    for key, val in fields.items():
        if _is_name_field(key) and val and val.strip():
            return val.strip()
    return ""


def _pick_phone(fields: Dict[str, str]) -> str:
    for key in ("phone", "phone_number", "mobile_phone", "telefon_raqamingizni_kiriting", "telefon_raqam", "telefon"):
        val = fields.get(key)
        if val and len(re.sub(r"\D", "", val)) >= 7:
            return val.strip()
    for key, val in fields.items():
        if _is_phone_field(key) and val and len(re.sub(r"\D", "", val)) >= 7:
            return val.strip()
    return fields.get("phone") or fields.get("phone_number") or ""


def _pick(fields: Dict[str, str], keys: set[str]) -> str:
    for key in keys:
        if fields.get(key):
            return fields[key]
    for key, value in fields.items():
        if key in keys or any(part in keys for part in key.split("_")):
            return value
    return ""


def _excluded_leadgen_keys(fields: Dict[str, str]) -> set[str]:
    return {k for k in fields if _is_name_field(k) or _is_phone_field(k) or _is_email_field(k)}
