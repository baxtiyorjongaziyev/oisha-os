"""Saytdagi "Sizga qo'ng'iroq qilamiz" so'rovi → AmoCRM lid + Telegram + vazifa.

OQIM:
    1. Telefon tekshiriladi va normallashtiriladi (+998XXXXXXXXX).
    2. AmoCRM'da aktiv bitim topiladi yoki ochiladi (`ensure_lead`);
       UTM / sahifa / referrer lid izohiga yoziladi — "qaysi reklama
       qo'ng'iroq olib keldi" savoliga javob shu yerdan.
    3. Sotuv guruhiga Telegram alert.
    4. Lidga "N daqiqada qo'ng'iroq qiling" vazifasi (default 5).

YOQISH: `CALLBACK_WIDGET_ENABLED=1` (default o'chiq).
QUIET HOURS: Telegram yo'q, vazifa ertalab 09:00 ga (missed_call_responder bilan bir xil).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from html import escape
from typing import Any, Dict, Optional

from src.services.call_analytics.missed_call_responder import callback_deadline
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger(__name__)

ENABLED_ENV = "CALLBACK_WIDGET_ENABLED"
SLA_ENV = "CALLBACK_REQUEST_SLA_MINUTES"
DEFAULT_SLA_MINUTES = 5
PHONE_DEDUP_SECONDS = 10 * 60

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
CLICK_ID_KEYS = ("fbclid", "gclid", "yclid")

_recent_phones: Dict[str, float] = {}


class InvalidPhoneError(ValueError):
    """Telefon raqami noto'g'ri."""


def is_enabled() -> bool:
    return (os.getenv(ENABLED_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def _sla_minutes() -> int:
    try:
        return max(1, int(os.getenv(SLA_ENV) or DEFAULT_SLA_MINUTES))
    except ValueError:
        return DEFAULT_SLA_MINUTES


def normalize_phone(raw: str) -> str:
    """O'zbekiston raqami → +998XXXXXXXXX; boshqa xalqaro raqam → +<raqamlar>."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if digits.startswith("998"):
        if len(digits) != 12:
            raise InvalidPhoneError("O'zbekiston raqami 12 raqamdan iborat bo'lishi kerak")
        return "+" + digits
    if 10 <= len(digits) <= 15:
        return "+" + digits
    raise InvalidPhoneError("Telefon raqami noto'g'ri")


def is_duplicate_phone(phone: str, now: Optional[float] = None) -> bool:
    """Bir raqamdan 10 daqiqada bir martadan ortiq so'rov — takror."""
    now = time.monotonic() if now is None else now
    for stale in [p for p, ts in _recent_phones.items() if now - ts > PHONE_DEDUP_SECONDS]:
        _recent_phones.pop(stale, None)
    if phone in _recent_phones:
        return True
    _recent_phones[phone] = now
    return False


def reset_dedup() -> None:
    """Testlar uchun."""
    _recent_phones.clear()


def source_label(tracking: Dict[str, str]) -> str:
    """Odam o'qiydigan manba: `instagram / cpc / kuzgi_aksiya` yoki `to'g'ridan-to'g'ri`."""
    parts = [tracking.get(k, "") for k in ("utm_source", "utm_medium", "utm_campaign")]
    parts = [p for p in parts if p]
    if parts:
        return " / ".join(parts)
    if tracking.get("gclid"):
        return "google (gclid)"
    if tracking.get("fbclid"):
        return "meta (fbclid)"
    referrer = tracking.get("referrer", "")
    return f"referrer: {referrer}" if referrer else "to'g'ridan-to'g'ri"


def build_note(name: str, phone: str, tracking: Dict[str, str]) -> str:
    lines = [
        "📲 Saytdan \"Sizga qo'ng'iroq qilamiz\" so'rovi",
        f"Ism: {name or '—'}",
        f"Telefon: {phone}",
        f"Manba: {source_label(tracking)}",
    ]
    for key in UTM_KEYS + CLICK_ID_KEYS:
        if tracking.get(key):
            lines.append(f"{key}: {tracking[key]}")
    for key, label in (("page_url", "Sahifa"), ("landing_url", "Kirish sahifasi"), ("referrer", "Referrer")):
        if tracking.get(key):
            lines.append(f"{label}: {tracking[key]}")
    return "\n".join(lines)


def build_alert(name: str, phone: str, tracking: Dict[str, str], lead_id: Optional[int], sla: int) -> str:
    lines = [
        "📲 <b>Saytdan qo'ng'iroq so'rovi!</b>",
        f"👤 {escape(name or 'Ism yozilmagan')}",
        f"📞 <code>{escape(phone)}</code>",
        f"🎯 Manba: {escape(source_label(tracking))}",
    ]
    if lead_id:
        lines.append(f"🔗 AmoCRM lid #{lead_id}")
    lines.append(f"⏱ <b>{sla} daqiqa ichida qo'ng'iroq qiling</b> — mijoz hozir issiq.")
    return "\n".join(lines)


def _get_amocrm() -> Any:
    from src.context import app_ctx
    amo = getattr(app_ctx, "amocrm_instance", None) or getattr(app_ctx, "amocrm", None)
    if amo is not None:
        return amo
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    return AmoCRMSync()


async def _send_alert(text: str) -> bool:
    from src.services.core.instagram.leadgen_watchdog import send_admin_alert
    return bool(await asyncio.to_thread(send_admin_alert, text))


async def handle_callback_request(
    name: str, phone: str, tracking: Dict[str, str],
    amocrm: Any = None, now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """So'rovni qayta ishlaydi. Telefon allaqachon normallashtirilgan bo'lishi kerak."""
    result: Dict[str, Any] = {"lead_id": None, "alert": False, "task": False}
    now = now or get_local_now()
    sla = _sla_minutes()
    amocrm = amocrm if amocrm is not None else _get_amocrm()
    label = name or phone
    try:
        result["lead_id"] = await amocrm.ensure_lead(
            name=f"Sayt: qo'ng'iroq so'rovi — {label}"[:250], phone=phone,
            note=build_note(name, phone, tracking),
        )
    except Exception as exc:
        logger.warning("[CALLBACK REQUEST] Lid ochilmadi (%s): %s", phone, exc)

    try:
        if is_quiet_hours(now):
            result["reason"] = "quiet_hours"
        else:
            result["alert"] = await _send_alert(build_alert(name, phone, tracking, result["lead_id"], sla))
        if result["lead_id"]:
            due = callback_deadline(now, sla)
            result["task"] = bool(await amocrm.create_task(
                element_id=int(result["lead_id"]),
                text=f"📲 Saytdan qo'ng'iroq so'rovi ({phone}) — qo'ng'iroq qiling",
                complete_till=int(due.timestamp()),
            ))
    except Exception as exc:
        logger.warning("[CALLBACK REQUEST] Alert/vazifa yiqildi (lead=%s): %s", result["lead_id"], exc)
    logger.info("[CALLBACK REQUEST] phone=%s source=%s result=%s", phone, source_label(tracking), result)
    return result
