"""Pure, LLM-free conversation signals (who wrote last, prices, cards, objections)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from src.services.core.card_watch.detector import extract_amount, find_card
from src.services.core.sales_copilot.transcript import Msg, Transcript

OUR_SIDES = {"manager", "staff"}
# Objection keywords (Uzbek latin/cyrillic + Russian), lower-case substrings.
OBJECTION_WORDS = (
    "qimmat", "қиммат", "дорого", "maslahatlash", "маслаҳатлаш", "посоветуюсь",
    "keyinroq", "кейинроқ", "keyin gaplash", "pul yoʼq", "pul yoq",
    "пул йўқ", "нет денег", "oʼylab koʼr", "oylab kor", "ўйлаб кўр", "подумаю",
    "arzonroq", "arzon", "скидка", "chegirma",
)
PRICE_WORDS = ("narx", "нарх", "цена", "стоимость", "soʻm", "so'm", "сум", "mln", "млн", "uzs")
_PRICE_RE = re.compile(r"\d[\d . ]{3,}\d|\d+\s*(mln|млн|million|ming|минг)", re.IGNORECASE)


@dataclass
class Signals:
    last_side: str = ""
    last_at: Optional[datetime] = None
    minutes_since_last: float = 0.0
    client_last_at: Optional[datetime] = None
    unanswered_question: bool = False
    objections: List[str] = field(default_factory=list)
    price_at: Optional[datetime] = None
    price_amount: Optional[float] = None
    card_at: Optional[datetime] = None
    card: str = ""
    card_amount: Optional[float] = None
    card_message: str = ""
    followups: int = 0  # our messages since the client's last message
    client_messages: int = 0
    our_messages: int = 0


def has_price(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in PRICE_WORDS) and bool(_PRICE_RE.search(text))


_APOSTROPHES = str.maketrans({"'": "ʼ", "ʻ": "ʼ", "`": "ʼ", "‘": "ʼ", "’": "ʼ"})


def find_objections(text: str) -> List[str]:
    low = text.lower().translate(_APOSTROPHES)
    return [w for w in OBJECTION_WORDS if w in low]


def compute(t: Transcript, now: datetime, cards: List[str]) -> Signals:
    s = Signals()
    msgs: List[Msg] = t.messages
    if not msgs:
        return s
    last = msgs[-1]
    s.last_side = "client" if last.side == "client" else "us"
    s.last_at = last.at
    s.minutes_since_last = max(0.0, (now - last.at).total_seconds() / 60)
    for m in msgs:
        if m.side == "client":
            s.client_messages += 1
            s.client_last_at = m.at
            s.followups = 0
            for w in find_objections(m.text):
                if w not in s.objections:
                    s.objections.append(w)
            continue
        s.our_messages += 1
        s.followups += 1
        card = find_card(m.text, cards)
        if card:
            s.card_at, s.card, s.card_message = m.at, card, m.text
            s.card_amount = extract_amount(m.text)
        elif has_price(m.text):
            s.price_at = m.at
            s.price_amount = extract_amount(m.text)
    if s.last_side == "client":
        tail = [m.text for m in reversed(msgs) if m.side == "client"][:3]
        s.unanswered_question = any("?" in x for x in tail)
    return s


def our_replies_after(t: Transcript, moment: datetime) -> int:
    return sum(1 for m in t.messages if m.side in OUR_SIDES and m.at > moment)
