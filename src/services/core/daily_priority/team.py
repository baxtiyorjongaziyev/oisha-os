"""Jamoa roʻyxati va rollar (egasi 2026-11-16 da tasdiqlagan)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DailyPriority")

ROLE_SALES = "sales"
ROLE_FINANCE = "finance"

DEFAULT_TEAM: List[Dict[str, Any]] = [
    {"key": "shahnoza", "name": "Shahnoza", "user_id": 8802892610,
     "username": "jonbranding_assistant", "role": ROLE_SALES},
    {"key": "rayxona", "name": "Rayxona", "user_id": 8878762085,
     "username": "RayxonJonbranding", "role": ROLE_SALES},
    {"key": "mumtozmaxal", "name": "Mumtozmaxal", "user_id": 8940413540,
     "username": "MumtozmaxalJonbranding", "role": ROLE_SALES},
    {"key": "dilbar", "name": "Dilbar", "user_id": 8611068511,
     "username": "jonbranding_finansist", "role": ROLE_FINANCE},
]


def get_team() -> List[Dict[str, Any]]:
    """`DAILY_PRIORITY_TEAM` (JSON) boʻlsa oʻsha, aks holda standart roʻyxat."""
    raw = os.getenv("DAILY_PRIORITY_TEAM", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data
        except ValueError:
            logger.warning("[DAILY] DAILY_PRIORITY_TEAM JSON emas, standart roʻyxat ishlatiladi.")
    return DEFAULT_TEAM


def find_member(user_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if user_id is None:
        return None
    for member in get_team():
        if int(member.get("user_id") or 0) == int(user_id):
            return member
    return None
