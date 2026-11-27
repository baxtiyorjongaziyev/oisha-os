"""Central phone-number blacklist for amoCRM sync and call analysis."""
from __future__ import annotations

from typing import Any, Iterable

from src.settings import settings as _default_settings


def _digits_only(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _iter_configured_phones(settings_obj: Any) -> Iterable[str]:
    excluded_list = getattr(settings_obj, "EXCLUDED_PHONES", None) or []
    for item in excluded_list:
        if item:
            yield str(item)

    raw_csv = getattr(settings_obj, "AMOCRM_CALL_ANALYSIS_EXCLUDED_PHONES", "") or ""
    for item in raw_csv.split(","):
        if item.strip():
            yield item.strip()


def is_excluded_phone(phone: str, settings_obj: Any = None) -> bool:
    """Return True if *phone* is in the amoCRM / call-analysis blacklist."""
    digits = _digits_only(phone)
    if not digits:
        return False
    cfg = settings_obj if settings_obj is not None else _default_settings
    local9 = digits[-9:] if len(digits) >= 9 else digits

    for entry in _iter_configured_phones(cfg):
        entry_digits = _digits_only(entry)
        if not entry_digits:
            continue
        entry_local9 = entry_digits[-9:] if len(entry_digits) >= 9 else entry_digits
        if digits == entry_digits or (len(local9) == 9 and local9 == entry_local9):
            return True
    return False
