"""Payment-promise extraction with source evidence.

Answers "kim qachon pul beraman degan?" from already-fetched messages
(amoCRM notes, call transcripts, Telegram). Every promise keeps who said it,
the exact quote, when it was said and its source id. Vague dates are never
guessed: they stay ``promised_date=None`` with ``date_ambiguous=True``.
Sources that could not be read are reported as unknown coverage instead of
being silently treated as "no promises".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

# Tashkent has no DST, so a fixed offset is exact and needs no tzdata.
TASHKENT_TZ = timezone(timedelta(hours=5), "Asia/Tashkent")

CLIENT = "client"
MANAGER = "manager"

_PAY_VERB = re.compile(
    r"\b(?:to'la(?:yman|ymiz|b\s+beraman|b\s+beramiz|ydi|ydilar)"
    r"|to'lov\s+qila(?:man|miz|di)"
    r"|pul(?:ni)?\s+(?:beraman|beramiz|tashlayman|tashlaymiz|o'tkazaman|o'tkazamiz|beradi)"
    r"|o'tkazib\s+beraman|o'tkazib\s+beramiz|tashlab\s+beraman|tashlab\s+beramiz"
    r"|o'tkazaman|o'tkazamiz)\b"
)
_NEGATION = re.compile(
    r"\b(?:to'lamay(?:man|miz)|to'lay\s+olmay(?:man|miz)|bera\s+olmay(?:man|miz)"
    r"|o'tkaza\s+olmay(?:man|miz)|pul\s+yo'q|to'lamaydi)\b"
)
_VAGUE = re.compile(
    r"\b(?:oy\s+oxiri\w*|keyingi\s+hafta\w*|bu\s+hafta\w*|tez\s+orada|imkon\s+bo'lsa"
    r"|yaqin\s+kunlar\w*|kelasi\s+oy\w*|keyinroq)\b"
)
_RELATIVE_DAYS = {"bugun": 0, "ertaga": 1, "indinga": 2}
_WEEKDAYS = {
    "dushanba": 0, "seshanba": 1, "chorshanba": 2, "payshanba": 3,
    "juma": 4, "shanba": 5, "yakshanba": 6,
}
_MONTHS = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "oktabr": 10, "noyabr": 11, "dekabr": 12,
}
_MONTH_DATE = re.compile(
    r"\b(\d{1,2})\s*-?\s*(?:chi\s+|-chi\s+)?(" + "|".join(_MONTHS) + r")\w*"
)
_DOTTED_DATE = re.compile(
    r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b(?!\s*(?:million|mln|ming))"
)
_AMOUNT = re.compile(
    r"(?P<usd>\$\s*)?(?P<num>\d{1,3}(?:[  ]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(?P<mult>million|mln|ming)?\s*(?P<cur>so'm|sum|dollar|usd)?"
)
_MULTIPLIERS = {"million": 1_000_000, "mln": 1_000_000, "ming": 1_000}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class SourceMessage:
    """One already-fetched message from a source system."""

    source: str  # e.g. "amocrm_note", "call_transcript", "telegram"
    source_id: str
    speaker: str
    speaker_role: str  # CLIENT or MANAGER
    said_at: datetime  # must be timezone-aware
    text: str
    lead_id: Optional[str] = None


@dataclass(frozen=True)
class PaymentPromise:
    """A payment promise with the evidence behind it."""

    source: str
    source_id: str
    lead_id: Optional[str]
    speaker: str
    speaker_role: str
    said_at: datetime
    quote: str
    promised_date: Optional[date]
    date_ambiguous: bool
    amount: Optional[int]
    currency: Optional[str]


@dataclass
class PromiseReport:
    """Promises plus explicit coverage of which sources were actually read."""

    promises: List[PaymentPromise] = field(default_factory=list)
    source_status: Dict[str, str] = field(default_factory=dict)

    @property
    def client_promises(self) -> List[PaymentPromise]:
        return [p for p in self.promises if p.speaker_role == CLIENT]

    @property
    def manager_forecasts(self) -> List[PaymentPromise]:
        return [p for p in self.promises if p.speaker_role == MANAGER]

    @property
    def unknown_sources(self) -> List[str]:
        return sorted(s for s, st in self.source_status.items() if st != "ok")

    @property
    def complete(self) -> bool:
        return bool(self.source_status) and not self.unknown_sources


def _normalize(text: str) -> str:
    """Lowercase and unify Uzbek apostrophe variants to a plain quote."""
    return re.sub(r"[’‘`ʻʼ]", "'", text or "").lower()


def _local_date(said_at: datetime) -> date:
    if said_at.tzinfo is None:
        raise ValueError("said_at must be timezone-aware")
    return said_at.astimezone(TASHKENT_TZ).date()


def _resolve_date(sentence: str, said_on: date) -> Tuple[Optional[date], bool]:
    """Return (date, ambiguous). Only explicit or day-relative wording resolves."""
    for word, offset in _RELATIVE_DAYS.items():
        if re.search(rf"\b{word}\b", sentence):
            return said_on + timedelta(days=offset), False

    m = _MONTH_DATE.search(sentence)
    if m:
        return _with_year(int(m.group(1)), _MONTHS[m.group(2)], None, said_on)

    m = _DOTTED_DATE.search(sentence)
    if m:
        year = int(m.group(3)) if m.group(3) else None
        if year is not None and year < 100:
            year += 2000
        return _with_year(int(m.group(1)), int(m.group(2)), year, said_on)

    for word, weekday in _WEEKDAYS.items():
        if re.search(rf"\b{word}\b", sentence):
            # Next occurrence strictly after the day it was said.
            ahead = (weekday - said_on.weekday() - 1) % 7 + 1
            return said_on + timedelta(days=ahead), False

    return None, True


def _with_year(
    day: int, month: int, year: Optional[int], said_on: date
) -> Tuple[Optional[date], bool]:
    try:
        candidate = date(year or said_on.year, month, day)
    except ValueError:
        return None, True
    if year is None and candidate < said_on:
        # "15-yanvar" said in December means next January.
        try:
            candidate = date(said_on.year + 1, month, day)
        except ValueError:
            return None, True
    return candidate, False


def _extract_amount(sentence: str) -> Tuple[Optional[int], Optional[str]]:
    for m in _AMOUNT.finditer(sentence):
        mult, cur, usd = m.group("mult"), m.group("cur"), m.group("usd")
        if not (mult or cur or usd):
            continue  # a bare number (date, phone) is not money
        raw = re.sub(r"[  ]", "", m.group("num")).replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            continue
        value *= _MULTIPLIERS.get(mult or "", 1)
        currency = "USD" if usd or cur in ("dollar", "usd") else "UZS"
        return int(round(value)), currency
    return None, None


def extract_promises(message: SourceMessage) -> List[PaymentPromise]:
    """Extract payment promises from one message, one per promising sentence."""
    said_on = _local_date(message.said_at)
    found: List[PaymentPromise] = []
    for raw_sentence in _SENTENCE_SPLIT.split(message.text or ""):
        quote = raw_sentence.strip()
        sentence = _normalize(quote)
        if not quote or not _PAY_VERB.search(sentence) or _NEGATION.search(sentence):
            continue
        promised, ambiguous = _resolve_date(sentence, said_on)
        if _VAGUE.search(sentence) and promised is None:
            ambiguous = True
        amount, currency = _extract_amount(sentence)
        found.append(
            PaymentPromise(
                source=message.source,
                source_id=message.source_id,
                lead_id=message.lead_id,
                speaker=message.speaker,
                speaker_role=message.speaker_role,
                said_at=message.said_at,
                quote=quote,
                promised_date=promised,
                date_ambiguous=ambiguous,
                amount=amount,
                currency=currency,
            )
        )
    return found


def build_promise_report(
    messages: Iterable[SourceMessage],
    source_status: Mapping[str, str],
) -> PromiseReport:
    """Collect promises from all messages; ``source_status`` maps source -> "ok"/reason."""
    report = PromiseReport(source_status=dict(source_status))
    for message in messages:
        report.promises.extend(extract_promises(message))
    report.promises.sort(key=lambda p: (p.promised_date is None, p.promised_date or date.max))
    return report
