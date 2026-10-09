"""Statik call tracking: har bir reklama kanaliga alohida raqam.

G'OYA:
    Saytda mijoz qaysi kanaldan kelgan bo'lsa, `[data-oisha-phone]` elementlarida
    o'sha kanalning raqami ko'rinadi (callback-widget.js, `data-call-tracking="1"`).
    Shu raqamga kiruvchi qo'ng'iroq kelganda, AmoCRM call note'ida tracking raqam
    topiladi va lidga "Qo'ng'iroq manbasi: instagram" izohi yoziladi.

SOZLASH (`CALL_TRACKING_NUMBERS`, JSON — manba → raqam):
    {"instagram": "+998712000001", "google": "+998712000002", "default": "+998712000000"}
    `default` — manbasi aniqlanmagan tashrifchilar uchun asosiy raqam.

QAYSI MAYDONDA "QAYSI RAQAMGA" YOZILADI:
    AmoCRM/telefoniya provayderiga qarab turlicha (`to`, `line`, `did`, matn ichida...).
    Shuning uchun mijoz raqami (`phone`) dan tashqari barcha maydonlar ichidan tracking
    raqam qidiriladi — oxirgi 9 raqam bo'yicha solishtiriladi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

from src.services.call_analytics.missed_call_responder import INBOUND_NOTE_TYPES, flatten_note
from src.services.core.leads.callback_request import InvalidPhoneError, normalize_phone

logger = logging.getLogger(__name__)

NUMBERS_ENV = "CALL_TRACKING_NUMBERS"
CLIENT_PHONE_KEYS = {"phone", "caller_phone", "from", "phone_number"}
_SOURCE_RE = re.compile(r"^[a-z0-9_.-]{1,40}$")
_DIGITS_RE = re.compile(r"\d[\d\s()+-]{7,}\d")
_DEDUP_TTL_SECONDS = 6 * 3600

_attributed: Dict[str, float] = {}


def load_numbers() -> Dict[str, str]:
    """Env'dan manba → normallashtirilgan raqam. Noto'g'ri yozuvlar tashlab yuboriladi."""
    raw = (os.getenv(NUMBERS_ENV) or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("[CALL TRACKING] %s JSON emas — call tracking o'chiq", NUMBERS_ENV)
        return {}
    if not isinstance(data, dict):
        return {}
    numbers: Dict[str, str] = {}
    for source, number in data.items():
        key = str(source).strip().lower()
        if not _SOURCE_RE.match(key):
            continue
        try:
            numbers[key] = normalize_phone(str(number))
        except InvalidPhoneError:
            logger.warning("[CALL TRACKING] '%s' uchun raqam noto'g'ri — tashlab yuborildi", key)
    return numbers


def is_enabled() -> bool:
    return bool(load_numbers())


def _tail(digits: str) -> str:
    return digits[-9:]


def source_for_number(number: str, numbers: Optional[Dict[str, str]] = None) -> Optional[str]:
    numbers = load_numbers() if numbers is None else numbers
    tail = _tail(re.sub(r"\D", "", number or ""))
    if len(tail) < 9:
        return None
    for source, tracked in numbers.items():
        if _tail(tracked) == tail:
            return source
    return None


def source_for_note(note: Dict[str, Any], numbers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    """Call note ichidan tracking raqamni topadi → {"source", "number"} yoki None."""
    numbers = load_numbers() if numbers is None else numbers
    if not numbers:
        return None
    for key, value in flatten_note(note).items():
        if key in CLIENT_PHONE_KEYS or not isinstance(value, (str, int)):
            continue
        for candidate in _DIGITS_RE.findall(str(value)):
            source = source_for_number(candidate, numbers)
            if source:
                return {"source": source, "number": numbers[source]}
    return None


def reset_dedup() -> None:
    """Testlar uchun."""
    _attributed.clear()


def _call_key(flat: Dict[str, Any]) -> str:
    for key in ("uniq", "call_id", "id"):
        if flat.get(key):
            return str(flat[key])
    return f"{flat.get('element_id')}:{flat.get('created_at')}"


def _seen(key: str, now: float) -> bool:
    for stale in [k for k, ts in _attributed.items() if now - ts > _DEDUP_TTL_SECONDS]:
        _attributed.pop(stale, None)
    if key in _attributed:
        return True
    _attributed[key] = now
    return False


async def attribute_inbound_call(note: Dict[str, Any], amocrm: Any) -> Optional[str]:
    """Kiruvchi qo'ng'iroq tracking raqamga kelgan bo'lsa — lidga manba izohini yozadi."""
    flat = flatten_note(note)
    if str(flat.get("note_type") or "").lower() not in INBOUND_NOTE_TYPES:
        return None
    if str(flat.get("element_type") or "2").lower() not in {"2", "lead", "leads"}:
        return None
    match = source_for_note(note)
    if not match or amocrm is None:
        return None
    try:
        lead_id = int(flat.get("element_id") or 0)
    except (TypeError, ValueError):
        return None
    if not lead_id or _seen(_call_key(flat), time.monotonic()):
        return None
    text = (
        f"📞 Qo'ng'iroq manbasi: {match['source']}\n"
        f"Tracking raqam: {match['number']}\n"
        f"Mijoz raqami: {flat.get('phone') or '—'}"
    )
    try:
        await asyncio.to_thread(amocrm.add_lead_note, lead_id, text)
    except Exception as exc:
        logger.warning("[CALL TRACKING] Izoh yozilmadi (lead=%s): %s", lead_id, exc)
        return None
    logger.info("[CALL TRACKING] lead=%s source=%s", lead_id, match["source"])
    return match["source"]


def public_config() -> Dict[str, Any]:
    """Saytdagi JS uchun: manba → raqam. Faqat ochiq telefon raqamlari."""
    return {"numbers": load_numbers()}
