"""
Facade for Callmaster Outbound Call Campaign Service.
Delegates to modular subpackage in src.services.core.callmaster.
"""
from src.services.core.callmaster.models import (
    DATA_FILE_ENV,
    Campaign,
    Contact,
    CallAttempt,
    normalize_phone,
    utc_now_iso,
    _new_id,
    _safe_int,
)
from src.services.core.callmaster.actions import build_oisha_action
from src.services.core.callmaster.store import CallmasterStore

__all__ = [
    "DATA_FILE_ENV",
    "Campaign",
    "Contact",
    "CallAttempt",
    "normalize_phone",
    "utc_now_iso",
    "_new_id",
    "_safe_int",
    "build_oisha_action",
    "CallmasterStore",
]
