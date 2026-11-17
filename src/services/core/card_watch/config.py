"""Runtime configuration for the card payment watcher (env-only, no settings.py edits)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import SecretStr

logger = logging.getLogger("CardWatch")

DEFAULT_CARDS = ("5614681918811393", "5614681919485106")
SALES_GROUP_ID = -1003854308552
AIRTABLE_BASE = "app8xoyx1XCumYFXV"
AIRTABLE_TABLE = "tblrqxqIzyrvg7XpQ"
GROUP_TITLE_MARKER = "| jon branding"


@dataclass(frozen=True)
class Manager:
    key: str
    name: str
    username: str
    topic_id: Optional[int]
    session: Optional[SecretStr] = field(default=None, repr=False)

    @property
    def session_env(self) -> str:
        return f"CARD_WATCH_SESSION_{self.key.upper()}"


DEFAULT_MANAGERS = (
    ("shahnoza", "Shahnoza", "jonbranding_assistant", 122),
    ("rayxona", "Rayxona", "RayxonJonbranding", 2976),
    ("mumtozmaxal", "Mumtozmaxal", "MumtozmaxalJonbranding", 120),
    ("hasanboy", "Hasanboy", "hasan_yahyo", None),
)


def _env_session(key: str) -> Optional[SecretStr]:
    raw = os.getenv(f"CARD_WATCH_SESSION_{key.upper()}", "").strip()
    return SecretStr(raw) if raw else None


def load_cards() -> List[str]:
    raw = os.getenv("CARD_WATCH_CARDS", "")
    cards = [c for c in ("".join(ch for ch in part if ch.isdigit()) for part in raw.split(",")) if len(c) >= 12]
    return cards or list(DEFAULT_CARDS)


def load_managers() -> List[Manager]:
    """Managers from CARD_WATCH_MANAGERS (JSON list) or defaults; sessions from env."""
    rows = [dict(key=k, name=n, username=u, topic_id=t) for k, n, u, t in DEFAULT_MANAGERS]
    raw = os.getenv("CARD_WATCH_MANAGERS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                rows = parsed
        except ValueError:
            logger.warning("[CARD_WATCH] CARD_WATCH_MANAGERS is not JSON; using defaults")
    out = []
    for r in rows:
        key = str(r.get("key", "")).strip().lower()
        if not key:
            continue
        topic = r.get("topic_id")
        out.append(Manager(
            key=key,
            name=str(r.get("name") or key),
            username=str(r.get("username") or "").lstrip("@"),
            topic_id=int(topic) if topic not in (None, "") else None,
            session=_env_session(key),
        ))
    return out


def grace_days() -> int:
    try:
        return max(1, int(os.getenv("CARD_WATCH_GRACE_DAYS", "2")))
    except ValueError:
        return 2


def lookback_days() -> int:
    try:
        return max(1, int(os.getenv("CARD_WATCH_LOOKBACK_DAYS", "14")))
    except ValueError:
        return 14


def is_enabled() -> bool:
    return os.getenv("CARD_WATCH_ENABLED", "0") == "1"
