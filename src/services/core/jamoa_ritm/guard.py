"""Hamroh qachon javob berishini hal qiladi: mention aniqlash va shovqindan himoya."""
from __future__ import annotations

import re
import time
from collections import deque
from typing import Callable, Optional


def _mention_re(bot_username: str) -> re.Pattern:
    return re.compile(rf"(?<![\w@])@{re.escape(bot_username.lstrip('@'))}\b", re.IGNORECASE)


def is_addressed(
    text: str,
    *,
    bot_username: Optional[str],
    bot_id: Optional[int],
    reply_to_user_id: Optional[int] = None,
) -> bool:
    """Xabar botga qaratilganmi: @mention yoki bot xabariga reply. Buyruqlar (``/...``) emas."""
    clean = (text or "").strip()
    if not clean or clean.startswith("/"):
        return False
    if bot_id and reply_to_user_id == bot_id:
        return True
    if not bot_username:
        return False
    return bool(_mention_re(bot_username).search(clean))


def extract_question(text: str, bot_username: Optional[str]) -> str:
    clean = (text or "").strip()
    if bot_username:
        clean = _mention_re(bot_username).sub(" ", clean)
    return " ".join(clean.split()).strip(" ,:;-")


class ReplyLimiter:
    """Har bir a'zo uchun pauza va umumiy daqiqalik chegara (guruh shovqinga to'lmasin)."""

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
