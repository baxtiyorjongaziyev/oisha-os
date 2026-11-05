"""Uchrashuv tasdig'i: vaqtni kim aytgani va ikki tomon tasdiqlagani aniqlanadi.

Qoida: mijoz faqat o'z vaqtini aytgan bo'lsa, uchrashuv TASDIQLANMAGAN.
Tasdiq uchun ikkinchi tomon aniq rozilik yozishi kerak.
Sof funksiyalar: tarmoq, DB va Telegram'ga tegmaydi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

CONFIRMED = "confirmed"
AWAITING_OUR_CONFIRMATION = "awaiting_our_confirmation"
AWAITING_CLIENT_CONFIRMATION = "awaiting_client_confirmation"
NO_MEETING = "no_meeting"

_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)(?!\d)|"
                      r"(?:soat|соат|час(?:ов)?)\s*([01]?\d|2[0-3])(?!\d)", re.IGNORECASE)
_AGREE_RE = re.compile(
    r"\b(ok|okay|ha|xop|xo'p|mayli|tushunarli|kelishdik|boramiz|kutaman|"
    r"хоп|мayli|майли|хўп|келишдик|боламиз|кутаман|договорились|подтверждаю)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Message:
    """Yozishmadagi bitta xabar. `from_client` - mijoz yozganmi."""

    from_client: bool
    text: str


def has_time_proposal(text: str) -> bool:
    """Xabarda aniq vaqt (16:00, soat 16) bor-yo'qligi."""
    return bool(_TIME_RE.search(text or ""))


def has_agreement(text: str) -> bool:
    """Xabarda aniq rozilik so'zi bor-yo'qligi."""
    return bool(_AGREE_RE.search(text or ""))


def classify_meeting(messages: Iterable[Message]) -> str:
    """Yozishma bo'yicha uchrashuv holatini qaytaradi.

    Oxirgi vaqt taklifini topadi va undan keyingi ikkinchi tomon rozilik xabarini
    qidiradi. Vaqt taklifi yo'q bo'lsa `no_meeting`.
    """
    proposer_is_client: bool | None = None
    confirmed = False
    for msg in messages:
        other_side = proposer_is_client is not None and msg.from_client != proposer_is_client
        if other_side and has_agreement(msg.text):
            confirmed = True
        elif has_time_proposal(msg.text):
            proposer_is_client = msg.from_client
            confirmed = False
    if proposer_is_client is None:
        return NO_MEETING
    if confirmed:
        return CONFIRMED
    return AWAITING_OUR_CONFIRMATION if proposer_is_client else AWAITING_CLIENT_CONFIRMATION


def pre_visit_warning(status: str) -> str | None:
    """Borishdan oldin ogohlantirish matni. Tasdiqlangan bo'lsa None."""
    if status == CONFIRMED:
        return None
    if status == AWAITING_OUR_CONFIRMATION:
        return ("Mijoz vaqt aytgan, lekin siz tasdiqlamagansiz. "
                "Avval 'shu vaqtda boramiz' deb yozing.")
    if status == AWAITING_CLIENT_CONFIRMATION:
        return "Siz vaqt taklif qildingiz, mijoz hali rozilik bermagan. Tasdiqni kuting."
    return "Uchrashuv vaqti yozishmada belgilanmagan."
