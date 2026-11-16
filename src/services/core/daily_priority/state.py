"""Kunlik holat va qisqa xotira (oxirgi 7 kun), JSON faylda.

Tuzilma: {"YYYY-MM-DD": {"<key>": {...yozuv...}}}
Yozuv maydonlari: task, lead_id, status, proposed_at, reply, reply_at,
nudge_sent, followup_sent, followup_reply.
Status: proposed | accepted | changed | done | declined.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger("DailyPriority")

STATE_FILE = "data/daily_priority_state.json"
KEEP_DAYS = 7

STATUS_PROPOSED = "proposed"
STATUS_ACCEPTED = "accepted"
STATUS_CHANGED = "changed"
STATUS_DONE = "done"
STATUS_DECLINED = "declined"


def _path() -> str:
    return os.getenv("DAILY_PRIORITY_STATE_FILE", STATE_FILE)


def load() -> Dict[str, Any]:
    try:
        with open(_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state: Dict[str, Any], today: str) -> None:
    cutoff = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    trimmed = {day: entries for day, entries in state.items() if day >= cutoff}
    path = _path()
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(trimmed, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("[DAILY] Holatni yozib boʻlmadi: %s", exc)


def get_entry(state: Dict[str, Any], day: str, key: str) -> Optional[Dict[str, Any]]:
    return (state.get(day) or {}).get(key)


def set_entry(state: Dict[str, Any], day: str, key: str, entry: Dict[str, Any]) -> None:
    state.setdefault(day, {})[key] = entry


def last_entry_before(state: Dict[str, Any], day: str, key: str) -> Optional[Dict[str, Any]]:
    """Bugundan oldingi eng soʻnggi yozuv (kechagi vaʼda uchun)."""
    for past in sorted((d for d in state if d < day), reverse=True):
        entry = (state.get(past) or {}).get(key)
        if entry:
            return {**entry, "day": past}
    return None
