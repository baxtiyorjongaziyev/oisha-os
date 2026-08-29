"""
Facade for CRMContactsAuditor.
Delegates to modular implementation in src.services.core.crm.auditor.
"""
from src.services.core.crm.auditor import (
    CRMContactsAuditor,
    normalize_phone,
    _maybe_await,
)

__all__ = [
    "CRMContactsAuditor",
    "normalize_phone",
    "_maybe_await",
]
