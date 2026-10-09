"""Kiruvchi qo'ng'iroqda mijoz kartasi (Ezzy "screen-pop" analogi).

MUAMMO:
    Mijoz qo'ng'iroq qilganda (telefon jiringlayotganda), menejer mijozning
    kimligi, qaysi loyiha bo'yicha gaplashilgani, oxirgi kelishuv va byudjetini
    bilmaydi. Natijada sovuq va noaniq muloqot boshlanadi.

YECHIM (Real vaqtda Telegram screen-pop):
    Telefoniya (Android MacroDroid / PBX) dan kiruvchi qo'ng'iroq signali kelganda,
    AmoCRM'dan 1-2 soniya ichida mijoz profili yig'iladi va menejerga
    Telegram'da quyidagi karta chiqariladi:
    - Mijoz ismi va kontakt ma'lumotlari
    - Ochiq bitim (lid nomi, etapi, byudjeti)
    - Mas'ul menejer
    - Oxirgi muloqot xulosasi / izohi
    - Call tracking bo'yicha manba
    - AmoCRM to'g'ridan-to'g'ri havolasi

AGAR RAQAM BAZADA BO'LMASA:
    "🆕 Yangi raqam — CRM'da topilmadi" kartasi chiqadi.

QUIET HOURS (23:00–07:00):
    Telegram alert yuborilmaydi (tungi tinchlik).
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.core.crm.task_notifier.formatter import STATUS_MAP
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger(__name__)

FLAG_ENV = "INCOMING_CALL_CARD_ENABLED"
_DEDUP_TTL_SECONDS = 60.0
_seen: Dict[str, float] = {}


def is_incoming_call_card_enabled() -> bool:
    val = (os.getenv(FLAG_ENV) or "0").strip().lower()
    return val in {"1", "true", "yes", "on", "active"}


def normalize_phone(phone: str) -> str:
    """Telefon raqamini tozalash va xalqaro formatga keltirish."""
    if not phone:
        return ""
    digits = re.sub(r"[^\d]", "", phone)
    if not digits:
        return ""
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    return f"+{digits}" if not phone.startswith("+") else phone.strip()


def _already_handled(key: str, now: float) -> bool:
    for stale in [k for k, ts in list(_seen.items()) if now - ts > _DEDUP_TTL_SECONDS]:
        _seen.pop(stale, None)
    if key in _seen:
        return True
    _seen[key] = now
    return False


def reset_dedup() -> None:
    """Testlar uchun dedup keshini tozalash."""
    _seen.clear()


def _lead_url(lead_id: Optional[int]) -> str:
    if not lead_id:
        return ""
    try:
        from src.settings import settings
        subdomain = (getattr(settings, "AMOCRM_SUBDOMAIN", "") or "").strip()
    except Exception:
        subdomain = ""
    subdomain = subdomain or os.getenv("AMOCRM_SUBDOMAIN", "jonbranding")
    return f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}"


def _format_money(amount: int) -> str:
    if amount <= 0:
        return "ko'rsatilmagan"
    formatted = f"{amount:,}".replace(",", " ")
    return f"{formatted} so'm"


def build_incoming_card(info: Dict[str, Any]) -> str:
    """Telegram uchun HTML formatdagi mijoz kartasini tayyorlash."""
    phone = info.get("phone", "")
    lines = [
        "📞 <b>Kiruvchi qo'ng'iroq!</b>",
        f"📱 Raqam: <code>{html.escape(phone or 'nomaʼlum')}</code>",
    ]

    manager = info.get("assigned_manager")
    if manager:
        lines.append(f"👨‍💼 Qabul qiluvchi: <b>{html.escape(str(manager))}</b>")

    if not info.get("found"):
        lines.append("")
        lines.append("🆕 <b>Yangi raqam — CRM'da topilmadi</b>")
        lines.append("💡 <i>Mijoz bilan gaplashgach, yangi lid ochishingiz mumkin.</i>")
        return "\n".join(lines)

    client_name = info.get("client_name") or "Noma'lum mijoz"
    lead_name = info.get("lead_name") or ""
    header_name = f"👤 <b>{html.escape(client_name)}</b>"
    if lead_name and lead_name != client_name:
        header_name += f' — <i>"{html.escape(lead_name)}"</i>'
    lines.append(header_name)

    lead_id = info.get("lead_id")
    status_name = info.get("status_name") or "Aktiv"
    if lead_id:
        lines.append(f"📊 Bosqich: <b>{html.escape(status_name)}</b> · Lid: #{lead_id}")

    budget = info.get("budget", 0)
    lines.append(f"💰 Byudjet: <b>{_format_money(budget)}</b>")

    responsible = info.get("responsible_name")
    if responsible:
        lines.append(f"🎯 Mas'ul: <b>{html.escape(str(responsible))}</b>")

    last_note = info.get("last_note")
    if last_note:
        lines.append(f"🕘 Oxirgi aloqa: <i>{html.escape(str(last_note)[:150])}</i>")

    source = info.get("source")
    if source:
        lines.append(f"🌐 Manba: <b>{html.escape(str(source))}</b>")

    url = _lead_url(lead_id)
    if url:
        lines.append(f'🔗 <a href="{html.escape(url)}">AmoCRM kartasini ochish</a>')

    return "\n".join(lines)


async def _fetch_client_info(phone: str, amocrm: Any) -> Dict[str, Any]:
    """AmoCRM dan mijoz va uning ochiq bitimini qidirish."""
    data: Dict[str, Any] = {"phone": phone, "found": False}
    if not amocrm or not phone:
        return data

    lead: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None

    try:
        if hasattr(amocrm, "get_contact_by_phone"):
            contact = await asyncio.to_thread(amocrm.get_contact_by_phone, phone)
        if hasattr(amocrm, "find_active_lead_by_phone"):
            lead = await asyncio.to_thread(amocrm.find_active_lead_by_phone, phone)
    except Exception as exc:
        logger.warning("[SCREEN-POP] AmoCRM qidiruvida xatolik: %s", exc)
        return data

    if not lead and not contact:
        return data

    data["found"] = True
    if contact:
        data["client_name"] = contact.get("name") or ""
        data["contact_id"] = contact.get("id")

    if lead:
        data["lead_id"] = lead.get("id")
        data["lead_name"] = lead.get("name") or data.get("client_name") or ""
        data["budget"] = int(lead.get("price") or 0)
        status_id = lead.get("status_id")
        data["status_name"] = STATUS_MAP.get(status_id, f"Bosqich #{status_id}" if status_id else "Ochiq")

        resp_id = lead.get("responsible_user_id")
        if resp_id:
            data["responsible_name"] = f"Menejer #{resp_id}"

        # Oxirgi izohni olish
        if hasattr(amocrm, "get_lead_notes") and data.get("lead_id"):
            try:
                notes = await amocrm.get_lead_notes(data["lead_id"])
                if notes and isinstance(notes, list):
                    first_note = notes[0]
                    text = first_note.get("text") or first_note.get("params", {}).get("text", "")
                    if text:
                        data["last_note"] = str(text).strip()
            except Exception as note_exc:
                logger.debug("[SCREEN-POP] Izoh olishda xatolik: %s", note_exc)

    return data


async def _send_card(text: str, target_chat_id: Optional[str] = None) -> bool:
    """Telegram orqali kartani sotuv guruhiga yoki xodimga yuborish."""
    if target_chat_id:
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if bot_token:
            import requests

            payload = {
                "chat_id": target_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            try:
                res = await asyncio.to_thread(
                    requests.post,
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json=payload,
                    timeout=5,
                )
                if res.status_code == 200:
                    return True
            except Exception as exc:
                logger.warning("[SCREEN-POP] Shaxsiy chatga yuborishda xatolik: %s", exc)

    from src.services.core.instagram.leadgen_watchdog import send_admin_alert

    return bool(await asyncio.to_thread(send_admin_alert, text))


async def handle_incoming_call(
    payload: Dict[str, Any],
    amocrm: Any = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Kiruvchi qo'ng'iroq bo'yicha to'liq oqim."""
    result: Dict[str, Any] = {"handled": False, "found": False, "alert_sent": False}
    if not is_incoming_call_card_enabled():
        result["reason"] = "disabled"
        return result

    raw_phone = str(payload.get("phone") or "").strip()
    phone = normalize_phone(raw_phone)
    if not phone:
        result["reason"] = "missing_phone"
        return result

    call_key = str(payload.get("call_id") or phone)
    if _already_handled(call_key, time.monotonic()):
        result["reason"] = "duplicate"
        return result

    now = now or get_local_now()
    if is_quiet_hours(now):
        result["handled"] = True
        result["reason"] = "quiet_hours"
        return result

    result["handled"] = True
    info: Dict[str, Any] = {"phone": phone, "found": False}

    if amocrm is not None:
        try:
            info = await asyncio.wait_for(_fetch_client_info(phone, amocrm), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("[SCREEN-POP] AmoCRM timeout (2.0s), asosiy karta yuboriladi: %s", phone)
        except Exception as exc:
            logger.error("[SCREEN-POP] Kutilmagan xatolik: %s", exc)

    if payload.get("manager"):
        info["assigned_manager"] = payload.get("manager")
    if payload.get("source"):
        info["source"] = payload.get("source")

    result["found"] = bool(info.get("found"))
    result["lead_id"] = info.get("lead_id")

    card_text = build_incoming_card(info)
    target_chat = payload.get("chat_id")
    result["alert_sent"] = await _send_card(card_text, target_chat)
    return result
