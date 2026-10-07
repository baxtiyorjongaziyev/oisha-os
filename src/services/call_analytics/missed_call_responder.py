"""Javobsiz kiruvchi qo'ng'iroqqa darhol reaksiya (Ezzy "auto-callback" analogi).

MUAMMO:
    `call_events` javobsiz qo'ng'iroqlarni faqat SANAYDI. Hech kim mijozga
    qayta qo'ng'iroq qilishga undalmaydi — mijoz shu orada raqobatchiga
    qo'ng'iroq qiladi.

YECHIM (AmoCRM `notes[add]` webhook'i orqali, real vaqtda):
    1. Kiruvchi qo'ng'iroq + gaplashilgan vaqt 0 → "javobsiz".
    2. Sotuv guruhiga Telegram alert: raqam, lid havolasi, mas'ul.
    3. AmoCRM'da lidga "15 daqiqada qayta qo'ng'iroq" vazifasi.

REJIM (`MISSED_CALL_RESPONDER_MODE`, default `off`):
    off   — hech narsa qilmaydi.
    alert — faqat Telegram alert.
    live  — Telegram alert + AmoCRM vazifa.

QUIET HOURS (23:00–07:00):
    Telegram alert yuborilmaydi; vazifa ertalab 09:00 ga qo'yiladi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from html import escape
from typing import Any, Dict, Optional

from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger(__name__)

MODE_ENV = "MISSED_CALL_RESPONDER_MODE"
SLA_ENV = "MISSED_CALL_CALLBACK_MINUTES"
MODES = {"off", "alert", "live"}
DEFAULT_SLA_MINUTES = 15
MORNING_HOUR = 9

# AmoCRM: 10 = call_in (v2 webhook raqamli), "call_in" (v4 nomli).
INBOUND_NOTE_TYPES = {"10", "call_in"}
# AmoCRM call_status: 4 = muvaffaqiyatli suhbat.
ANSWERED_STATUS = "4"
CONTACT_ELEMENT_TYPES = {"1", "contact", "contacts"}

_DEDUP_TTL_SECONDS = 6 * 3600
_seen: Dict[str, float] = {}


def get_mode() -> str:
    mode = (os.getenv(MODE_ENV) or "off").strip().lower()
    return mode if mode in MODES else "off"


def _sla_minutes() -> int:
    try:
        return max(1, int(os.getenv(SLA_ENV) or DEFAULT_SLA_MINUTES))
    except ValueError:
        return DEFAULT_SLA_MINUTES


def flatten_note(note: Dict[str, Any]) -> Dict[str, Any]:
    """Webhook formati turlicha: params ichida, tekis, yoki `text` da JSON.

    Hammasini bitta kichik harfli lug'atga yig'amiz.
    """
    flat: Dict[str, Any] = {}
    text = note.get("text")
    if isinstance(text, str) and text.strip().startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                flat.update({str(k).lower(): v for k, v in parsed.items()})
        except ValueError:
            pass
    params = note.get("params")
    if isinstance(params, dict):
        flat.update({str(k).lower(): v for k, v in params.items()})
    flat.update({str(k).lower(): v for k, v in note.items() if k != "params"})
    return flat


def _duration(flat: Dict[str, Any]) -> Optional[int]:
    """Gaplashilgan soniya; kalit umuman bo'lmasa — None (noma'lum)."""
    for key in ("duration", "duration_seconds", "call_duration"):
        if key in flat and flat[key] not in (None, ""):
            try:
                return max(0, int(float(flat[key])))
            except (TypeError, ValueError):
                return None
    return None


def is_missed_inbound(note: Dict[str, Any]) -> bool:
    """Kiruvchi va javob berilmagan qo'ng'iroqmi?

    Davomiylik noma'lum bo'lsa — javobsiz DEMAYMIZ (soxta alert yomonroq).
    """
    flat = flatten_note(note)
    if str(flat.get("note_type") or "").lower() not in INBOUND_NOTE_TYPES:
        return False
    if str(flat.get("call_status") or "") == ANSWERED_STATUS:
        return False
    return _duration(flat) == 0


def _call_key(flat: Dict[str, Any]) -> str:
    for key in ("uniq", "call_id", "id"):
        if flat.get(key):
            return str(flat[key])
    return f"{flat.get('element_id')}:{flat.get('phone')}:{flat.get('created_at')}"


def _already_handled(key: str, now: float) -> bool:
    for stale in [k for k, ts in _seen.items() if now - ts > _DEDUP_TTL_SECONDS]:
        _seen.pop(stale, None)
    if key in _seen:
        return True
    _seen[key] = now
    return False


def reset_dedup() -> None:
    """Testlar uchun."""
    _seen.clear()


def callback_deadline(now: datetime, sla_minutes: int) -> datetime:
    """Vazifa muddati: odatda now+SLA, quiet hours'da ertalab 09:00."""
    if not is_quiet_hours(now):
        return now + timedelta(minutes=sla_minutes)
    morning = now.replace(hour=MORNING_HOUR, minute=0, second=0, microsecond=0)
    return morning if now.hour < MORNING_HOUR else morning + timedelta(days=1)


def _lead_url(lead_id: Optional[int]) -> str:
    if not lead_id:
        return ""
    try:
        from src.settings import settings
        subdomain = (getattr(settings, "AMOCRM_SUBDOMAIN", "") or "").strip()
    except Exception:
        subdomain = ""
    return f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}" if subdomain else ""


def build_alert(
    phone: str, lead_id: Optional[int], sla_minutes: int, when: datetime, source: Optional[str] = None,
) -> str:
    lines = [
        "📵 <b>Javobsiz qo'ng'iroq!</b>",
        f"📞 Raqam: <code>{escape(phone or 'nomaʼlum')}</code>",
        f"🕒 Vaqt: {when.strftime('%H:%M')}",
    ]
    if source:
        lines.append(f"🎯 Manba: {escape(source)}")
    url = _lead_url(lead_id)
    if url:
        lines.append(f'🔗 <a href="{escape(url)}">AmoCRM lid #{lead_id}</a>')
    lines.append(f"⏱ <b>{sla_minutes} daqiqa ichida qayta qo'ng'iroq qiling</b> — mijoz raqobatchiga ketmasin.")
    return "\n".join(lines)


def _lead_id(flat: Dict[str, Any]) -> Optional[int]:
    if str(flat.get("element_type") or "").lower() in CONTACT_ELEMENT_TYPES:
        return None
    try:
        return int(flat.get("element_id") or 0) or None
    except (TypeError, ValueError):
        return None


def _tracked_source(note: Dict[str, Any]) -> Optional[str]:
    """Call tracking yoqilgan bo'lsa — qo'ng'iroq qaysi kanal raqamiga kelgani."""
    try:
        from src.services.core.leads.call_tracking import source_for_note
        match = source_for_note(note)
    except Exception as exc:
        logger.debug("[MISSED CALL] Manba aniqlanmadi: %s", exc)
        return None
    return match["source"] if match else None


async def _send_alert(text: str) -> bool:
    from src.services.core.instagram.leadgen_watchdog import send_admin_alert
    return bool(await asyncio.to_thread(send_admin_alert, text))


async def _create_task(amocrm: Any, lead_id: int, phone: str, due: datetime, responsible: Any) -> bool:
    text = f"📵 Javobsiz qo'ng'iroq ({phone or 'raqam nomaʼlum'}) — qayta qo'ng'iroq qiling"
    try:
        responsible_id = int(responsible) if responsible else None
    except (TypeError, ValueError):
        responsible_id = None
    result = await amocrm.create_task(
        element_id=lead_id, text=text,
        complete_till=int(due.timestamp()), responsible_user_id=responsible_id,
    )
    return bool(result)


async def handle_missed_call_note(
    note: Dict[str, Any], amocrm: Any = None, now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Bitta AmoCRM note uchun javobsiz-qo'ng'iroq oqimi. Hech qachon raise qilmaydi."""
    result: Dict[str, Any] = {"handled": False, "alert": False, "task": False}
    mode = get_mode()
    if mode == "off" or not is_missed_inbound(note):
        return result
    flat = flatten_note(note)
    if _already_handled(_call_key(flat), time.monotonic()):
        result["reason"] = "duplicate"
        return result

    now = now or get_local_now()
    sla = _sla_minutes()
    phone = str(flat.get("phone") or "").strip()
    lead_id = _lead_id(flat)
    result["handled"] = True
    try:
        if is_quiet_hours(now):
            result["reason"] = "quiet_hours"
        else:
            result["alert"] = await _send_alert(build_alert(phone, lead_id, sla, now, _tracked_source(note)))
        if mode == "live" and lead_id and amocrm is not None:
            due = callback_deadline(now, sla)
            result["task"] = await _create_task(amocrm, lead_id, phone, due, flat.get("responsible_user_id"))
    except Exception as exc:
        logger.warning("[MISSED CALL] Oqim yiqildi (lead=%s): %s", lead_id, exc)
    logger.info("[MISSED CALL] lead=%s mode=%s result=%s", lead_id, mode, result)
    return result
