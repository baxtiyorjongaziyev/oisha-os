"""Guruhda botga murojaatni aniqlash (mention, ism, reply) va shovqindan himoya.

Qoida (docs/agents/bot-personas.md #8):
- Har bot faqat oʻz ismi ("Oisha") yoki @username bilan belgilanganda (yoki oʻz xabariga
  reply qilinsa) javob beradi.
- Agar xabarda boshqa bot ismi ("Amina", "Mr.Jon", "@jon_clawbot") tilga olingan boʻlsa va
  shu botning oʻzi chaqirilmagan boʻlsa — jim turadi (hatto reply qilingan boʻlsa ham).
"""
from __future__ import annotations

import re
import time
from collections import deque
from typing import Callable, Iterable, Optional

DEFAULT_SELF_NAMES: tuple[str, ...] = ("oisha", "оиша")
DEFAULT_OTHER_BOT_NAMES: tuple[str, ...] = (
    "amina",
    "амина",
    "mr.jon",
    "mr jon",
    "mrjon",
    "мистер джон",
    "jon_clawbot",
)


def _mention_re(bot_username: str) -> re.Pattern:
    return re.compile(rf"(?<![\w@])@{re.escape(bot_username.lstrip('@'))}\b", re.IGNORECASE)


def _name_re(names: Iterable[str]) -> Optional[re.Pattern]:
    cleaned = [re.escape(n.strip().lstrip("@")) for n in names if n and n.strip()]
    if not cleaned:
        return None
    joined = "|".join(cleaned)
    return re.compile(rf"(?<![\w@])@?(?:{joined})(?:xon|jon|ga|dan|ni|ning)?\b", re.IGNORECASE)


def is_addressed(
    text: str,
    *,
    bot_username: Optional[str],
    bot_id: Optional[int],
    reply_to_user_id: Optional[int] = None,
    self_names: Iterable[str] = DEFAULT_SELF_NAMES,
    other_bot_names: Iterable[str] = DEFAULT_OTHER_BOT_NAMES,
) -> bool:
    """Xabar shu botga qaratilganmi: @mention, oʻz ismi yoki bot xabariga reply (boshqa bot chaqirilmaganda)."""
    clean = (text or "").strip()
    if not clean or clean.startswith("/"):
        return False

    has_self_username = bool(bot_username and _mention_re(bot_username).search(clean))
    self_pattern = _name_re(self_names)
    has_self_name = bool(self_pattern and self_pattern.search(clean))

    if has_self_username or has_self_name:
        return True

    other_pattern = _name_re(other_bot_names)
    if other_pattern and other_pattern.search(clean):
        return False

    if bot_id and reply_to_user_id == bot_id:
        return True

    return False


def extract_question(
    text: str,
    bot_username: Optional[str],
    *,
    self_names: Iterable[str] = DEFAULT_SELF_NAMES,
) -> str:
    clean = (text or "").strip()
    if bot_username:
        clean = _mention_re(bot_username).sub(" ", clean)
    cleaned_names = [re.escape(n.strip()) for n in self_names if n and n.strip()]
    if cleaned_names:
        vocative_re = re.compile(
            rf"^\s*(?:{'|'.join(cleaned_names)})(?:xon|jon)?\b[\s,:;!\-]*",
            re.IGNORECASE,
        )
        clean = vocative_re.sub("", clean)
    return " ".join(clean.split()).strip(" ,:;-")


class ReplyLimiter:
    """Har bir aʼzo uchun pauza va umumiy daqiqalik chegara (guruh shovqinga toʻlmasin)."""

    def __init__(
        self,
        per_user_seconds: float = 10.0,
        max_per_window: int = 8,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._per_user = per_user_seconds
        self._max = max_per_window
        self._window = window_seconds
        self._clock = clock
        self._last_by_user: dict[int, float] = {}
        self._recent: deque[float] = deque()

    def allow(self, user_id: int) -> bool:
        now = self._clock()
        while self._recent and now - self._recent[0] >= self._window:
            self._recent.popleft()
        last = self._last_by_user.get(user_id)
        if last is not None and now - last < self._per_user:
            return False
        if len(self._recent) >= self._max:
            return False
        self._last_by_user[user_id] = now
        self._recent.append(now)
        return True
