"""
Environment helpers and timing heuristics for background monitor loop.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

logger = logging.getLogger("OishaScheduler")


def _env_int(name: str, default: int, min_val: int = 0, max_val: int = 86400) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        parsed = int(val.strip())
        return max(min_val, min(parsed, max_val))
    except ValueError:
        return default


def _is_due(now: datetime, hour: int, minute: int, window_min: int = 10) -> bool:
    """True if now is within [minute, minute+window_min) of the given hour."""
    if now.hour != hour:
        return False
    return minute <= now.minute < (minute + window_min)
