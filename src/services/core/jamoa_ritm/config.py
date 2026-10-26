"""Jamoa ritmi va Hamroh sozlamalari.

Qiymatlar muhit o'zgaruvchilaridan o'qiladi (``settings.py`` coordinator fayliga tegmaslik
uchun; ``AppSettings`` noma'lum kalitlarni e'tiborsiz qoldiradi):

- ``JAMOA_GROUP_ID``        — jamoa guruhi ID'si. Berilmasa funksiya butunlay o'chiq.
- ``JAMOA_OWNER_ID``        — o'z-o'zini tahlil hisoboti boradigan shaxs (standart: ``OWNER_ID``).
- ``JAMOA_RITM_ENABLED``    — jadvaldagi xabarlar (standart: yoqiq).
- ``JAMOA_HAMROH_ENABLED``  — guruhni kuzatish va mention'ga javob (standart: yoqiq).
- ``DISABLE_UNSOLICITED_REPORTS=1`` — umumiy kill-switch: jadvaldagi xabarlar yuborilmaydi.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_int(name: str) -> Optional[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return default


@dataclass(frozen=True)
class JamoaConfig:
    group_id: Optional[int]
    owner_id: Optional[int]
    ritm_enabled: bool
    hamroh_enabled: bool

    @property
    def ritm_active(self) -> bool:
        return self.group_id is not None and self.ritm_enabled

    @property
    def hamroh_active(self) -> bool:
        return self.group_id is not None and self.hamroh_enabled


def load_config(settings_obj: Any = None) -> JamoaConfig:
    if settings_obj is None:
        from src.settings import settings as settings_obj
    owner = _env_int("JAMOA_OWNER_ID") or int(getattr(settings_obj, "OWNER_ID", 0) or 0) or None
    unsolicited_off = (os.getenv("DISABLE_UNSOLICITED_REPORTS") or "").strip() == "1"
    return JamoaConfig(
        group_id=_env_int("JAMOA_GROUP_ID"),
        owner_id=owner,
        ritm_enabled=_env_flag("JAMOA_RITM_ENABLED", True) and not unsolicited_off,
        hamroh_enabled=_env_flag("JAMOA_HAMROH_ENABLED", True),
    )
