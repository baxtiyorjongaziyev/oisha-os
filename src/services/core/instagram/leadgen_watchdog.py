"""Autonomous 24/7 self-healing watchdog for Meta Lead Ads triple-channel delivery."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import requests
from typing import Any, Dict, List, Optional

from src.services.core.instagram.leadgen_delivery import (
    get_pending_deliveries,
    mark_channel_delivered,
    increment_delivery_retry,
    get_delivery_summary,
)
from src.services.core.instagram.leadgen_dedup import is_leadgen_processed, mark_leadgen_processed

logger = logging.getLogger("LeadgenWatchdog")

# Router checkpoints the lead (telegram_ok=0) before it sends the alert; retrying a
# fresh row races the in-flight router and produces a duplicate Telegram card.
_IN_FLIGHT_GRACE_SEC = int(os.getenv("LEADGEN_WATCHDOG_GRACE_SEC", "600"))


_DISPATCHED_SOS: set[str] = set()


def send_lead_sos_alert(leadgen_id: str, lead_id: Optional[int], channel: str, error: str) -> bool:
    """Send emergency SOS alert to sales/admin topic when a delivery channel repeatedly fails."""
    sos_key = f"{leadgen_id}_{channel}"
    if sos_key in _DISPATCHED_SOS:
        return False

    sos_text = (
        "🚨 <b>[OISHA SOS: LID YETKAZISHDA XATOLIK]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Meta Lid ID:</b> <code>{leadgen_id}</code>\n"
        f"🧾 <b>AmoCRM Bitim:</b> <code>{lead_id or 'Ochilmadi'}</code>\n"
        f"❌ <b>Yetkazilmagan kanal:</b> <b>{channel.upper()}</b>\n"
        f"❗️ <b>Xatolik:</b> <code>{error[:250]}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 <i>Watchdog qayta urinmoqda. Zudlik bilan tekshiring!</i>"
    )
    if send_admin_alert(sos_text):
        _DISPATCHED_SOS.add(sos_key)
        logger.warning("[WATCHDOG SOS] Dispatched SOS alert for %s channel=%s", leadgen_id, channel)
        return True
    return False


def send_admin_alert(text: str, technical: bool = False) -> bool:
    """Post an HTML alert. Returns True on HTTP 200.

    technical=True routes to the tech alert chat (TELEGRAM_ALERT_CHAT_ID), not the sales group.
    """
    from src.settings import settings
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    getter = getattr(getattr(settings, "BOT_TOKEN", None), "get_secret_value", None)
    if callable(getter):
        bot_token = getter() or bot_token

    if technical:
        chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID") or "-1003792973489"
        topic_id = os.getenv("TELEGRAM_ALERT_TOPIC_ID") or ""
    else:
        chat_id = getattr(settings, "TARGET_LEADS_GROUP_ID", None) or os.getenv("TARGET_LEADS_GROUP_ID", "-1003854308552")
        topic_id = getattr(settings, "TARGET_LEADS_TOPIC_ID", None) or os.getenv("TARGET_LEADS_TOPIC_ID", 1020)
    if not bot_token or not chat_id:
        return False

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if topic_id:
        try:
            payload["message_thread_id"] = int(topic_id)
        except (ValueError, TypeError):
            pass

    try:
        res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload, timeout=10)
        return res.status_code == 200
    except Exception as exc:
        logger.error("[WATCHDOG SOS] Failed to dispatch alert: %s", type(exc).__name__)
    return False


async def retry_pending_leadgen_deliveries() -> int:
    """Scan and retry any lead that failed AmoCRM, Sheets, or Telegram delivery."""
    pending = get_pending_deliveries(limit=20, min_age_seconds=_IN_FLIGHT_GRACE_SEC)
    if not pending:
        return 0

    from src.services.core.instagram.leadgen_router import (
        _notify_telegram,
        build_telegram_message,
        _fetch_leadgen_payload,
        flatten_field_data,
        _pick,
        _pick_name,
        _pick_phone,
        _amocrm_instance,
        DESTINATION_LABELS,
        PIPELINE_LABELS,
    )
    from src.services.core.instagram.leadgen_sheets import append_lead_to_sheet
    from src.services.core.crm.amocrm_pipeline_config import (
        UTC_PIPELINE_ID,
        UTC_NEW_STATUS_ID,
        TARGET_LEADS_INHOUSE_PIPELINE_ID,
        TARGET_LEADS_INHOUSE_NEW_STATUS_ID,
    )

    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    recovered_count = 0

    for item in pending:
        leadgen_id = str(item["leadgen_id"])
        lead_id = item.get("lead_id")
        amocrm_ok = bool(item.get("amocrm_ok"))
        sheets_ok = bool(item.get("sheets_ok"))
        telegram_ok = bool(item.get("telegram_ok"))
        destination = item.get("destination")
        retries = int(item.get("retries") or 0)
        if destination not in ("utc", "inhouse"):
            # Taqsimot yozilmagan bo'lsa taxmin qilmaymiz (noto'g'ri voronkaga tushmasin).
            logger.warning("[WATCHDOG] destination missing, skip leadgen_id=%s", leadgen_id)
            continue

        if destination == "inhouse":
            pipe_id = TARGET_LEADS_INHOUSE_PIPELINE_ID
            stat_id = TARGET_LEADS_INHOUSE_NEW_STATUS_ID
        else:
            pipe_id = UTC_PIPELINE_ID
            stat_id = UTC_NEW_STATUS_ID
        dest_label = DESTINATION_LABELS[destination]

        payload: Dict[str, Any] = {}
        if token:
            payload = await asyncio.to_thread(_fetch_leadgen_payload, leadgen_id, token)

        fields = flatten_field_data(payload.get("field_data") or [])
        name = _pick_name(fields) or "Mijoz"
        phone = _pick_phone(fields)
        email = fields.get("email") or fields.get("email_address") or ""
        form_name = str(payload.get("form_name") or payload.get("form_id") or "")

        # 1. Retry AmoCRM
        if not amocrm_ok or not lead_id:
            try:
                amocrm = _amocrm_instance()
                if phone:
                    lead_id = await amocrm.ensure_lead(
                        name=name,
                        phone=phone,
                        note="[WATCHDOG AUTO-RETRY] Meta lead",
                        pipeline_id=pipe_id,
                        status_id=stat_id,
                    )
                if lead_id:
                    mark_channel_delivered(leadgen_id, "amocrm")
                    amocrm_ok = True
                    logger.info("[WATCHDOG] AmoCRM recovered leadgen_id=%s amo_id=%s", leadgen_id, lead_id)
            except Exception as e:
                err_msg = f"amocrm_err: {e}"
                increment_delivery_retry(leadgen_id, err_msg)
                if retries >= 1:
                    send_lead_sos_alert(leadgen_id, lead_id, "amocrm", err_msg)

        # 2. Retry Google Sheets
        if not sheets_ok:
            try:
                res = await asyncio.to_thread(
                    append_lead_to_sheet, leadgen_id, lead_id, fields, form_name, destination=destination
                )
                if res:
                    mark_channel_delivered(leadgen_id, "sheets")
                    sheets_ok = True
                    logger.info("[WATCHDOG] Google Sheets recovered leadgen_id=%s", leadgen_id)
            except Exception as e:
                err_msg = f"sheets_err: {e}"
                increment_delivery_retry(leadgen_id, err_msg)
                if retries >= 1:
                    send_lead_sos_alert(leadgen_id, lead_id, "sheets", err_msg)

        # 3. Retry Telegram
        if not telegram_ok and fields:
            try:
                msg = build_telegram_message(
                    leadgen_id, lead_id, name, phone, email, fields,
                    pipeline_name=PIPELINE_LABELS[destination], destination_label=dest_label,
                )
                tg_res = await asyncio.to_thread(_notify_telegram, msg)
                if tg_res:
                    mark_channel_delivered(leadgen_id, "telegram")
                    telegram_ok = True
                    mark_leadgen_processed(leadgen_id, lead_id=lead_id)
                    logger.info("[WATCHDOG] Telegram alert recovered leadgen_id=%s", leadgen_id)
            except Exception as e:
                err_msg = f"telegram_err: {e}"
                increment_delivery_retry(leadgen_id, err_msg)
                if retries >= 1:
                    send_lead_sos_alert(leadgen_id, lead_id, "telegram", err_msg)

        if amocrm_ok and sheets_ok and telegram_ok:
            recovered_count += 1

    return recovered_count


_META_COUNT_TTL_SEC = 600
_meta_count_cache: Dict[str, Any] = {"at": 0.0, "value": None}


def _meta_lifetime_leads_count() -> Optional[int]:
    """Sum of `leads_count` over every page form (all-time). None when Meta is unreachable.

    Cached for 10 min: the heartbeat calls audit_leadgen_health() every 30s.
    """
    if _meta_count_cache["at"] and time.monotonic() - _meta_count_cache["at"] < _META_COUNT_TTL_SEC:
        return _meta_count_cache["value"]
    from src.schedulers import meta_leadgen_scheduler as m

    try:
        token = m._get_page_token()
    except Exception:
        token = ""
    if not token:
        return None
    page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()
    version = os.getenv("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    url = f"https://graph.facebook.com/{version}/{page_id}/leadgen_forms"
    try:
        forms = m._get_pages(url, token, "id,leads_count")
    except Exception as exc:
        logger.warning("[WATCHDOG] Meta form count failed: %s", type(exc).__name__)
        return None
    total = sum(int(f.get("leads_count") or 0) for f in forms)
    _meta_count_cache.update(at=time.monotonic(), value=total)
    return total


def audit_leadgen_health() -> Dict[str, Any]:
    """Perform a 3-system audit across Meta Graph API, AmoCRM, Sheets, and Telegram."""
    summary = get_delivery_summary(hours=24)
    meta_count = _meta_lifetime_leads_count()

    return {
        "meta_total_forms_leads": meta_count,
        "last_24h_total": summary["total"],
        "last_24h_amocrm": summary["amocrm_ok"],
        "last_24h_sheets": summary["sheets_ok"],
        "last_24h_telegram": summary["telegram_ok"],
        "pending_retries": summary["pending"],
        "status": "healthy" if summary["pending"] == 0 else "recovering",
    }
