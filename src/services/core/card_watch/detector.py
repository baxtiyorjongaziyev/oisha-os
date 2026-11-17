"""Pure helpers: find company card numbers and amounts in message text."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

_SEP = r"[ \-\u00a0]?"
# 16-digit card in 4-digit groups, or a plain 12-19 digit run.
_DIGIT_RUN = re.compile(rf"(?<!\d)(?:\d{{4}}{_SEP}\d{{4}}{_SEP}\d{{4}}{_SEP}\d{{4}}|\d{{12,19}})(?!\d)")
_AMOUNT = re.compile(
    r"(\d{1,3}(?:[ .,\u00a0]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(mln|million|миллион|млн|ming|минг|тыс|k|so['ʻʼ`]?m|сум|uzs)?",
    re.IGNORECASE,
)
_MIN_AMOUNT = 10_000


@dataclass(frozen=True)
class CardSend:
    manager_key: str
    chat_id: int
    chat_title: str
    client_name: str
    message_id: int
    sent_at: datetime
    amount: Optional[float]
    card: str

    @property
    def uid(self) -> str:
        # Group message ids are shared by all members, so groups dedupe across accounts.
        if self.chat_id < 0:
            return f"g:{self.chat_id}:{self.message_id}"
        return f"{self.manager_key}:{self.chat_id}:{self.message_id}"


def find_card(text: str, cards: Iterable[str]) -> Optional[str]:
    """Return the company card mentioned in ``text`` (spaces/dashes tolerated)."""
    if not text:
        return None
    wanted = set(cards)
    for run in _DIGIT_RUN.findall(text):
        digits = re.sub(r"\D", "", run)
        for card in wanted:
            if card in digits:
                return card
    return None


def extract_amount(text: str) -> Optional[float]:
    """Best-effort UZS amount: largest plausible number, card digits removed."""
    if not text:
        return None
    cleaned = _DIGIT_RUN.sub(" ", text)
    best: Optional[float] = None
    for num, unit in _AMOUNT.findall(cleaned):
        value = _to_float(num)
        if value is None:
            continue
        u = (unit or "").lower()
        if u in {"mln", "million", "миллион", "млн"}:
            value *= 1_000_000
        elif u in {"ming", "минг", "тыс", "k"}:
            value *= 1_000
        if value >= _MIN_AMOUNT and (best is None or value > best):
            best = value
    return best


def _to_float(num: str) -> Optional[float]:
    s = num.replace("\u00a0", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ .,]\d{3})+", s):
        s = re.sub(r"[ .,]", "", s)
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None
