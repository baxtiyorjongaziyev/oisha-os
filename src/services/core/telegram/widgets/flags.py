"""Feature flags for widgets.

WIDGETS_ENABLED=1 turns widgets on. WIDGETS_MODULES=reports,approvals limits
them to named modules; empty or "*" means every module.
"""
from __future__ import annotations

import os
from typing import Optional

_TRUE = {"1", "true", "yes", "on"}


def widgets_enabled(module: Optional[str] = None) -> bool:
    if os.getenv("WIDGETS_ENABLED", "0").strip().lower() not in _TRUE:
        return False
    if module is None:
        return True
    raw = os.getenv("WIDGETS_MODULES", "").strip()
    if not raw or raw == "*":
        return True
    allowed = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return module.strip().lower() in allowed
