"""Autonomous 24/7 self-healing watchdog for Meta Lead Ads triple-channel delivery."""
from __future__ import annotations

import asyncio
import logging
import os
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

    from src.settings import settings
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    getter = getattr(getattr(settings, "BOT_TOKEN", None), "get_secret_value", None)
    if callable(getter):
        bot_token = getter() or bot_token

    chat_id = getattr(settings, "TARGET_LEADS_GROUP_ID", None) or os.getenv("TARGET_LEADS_GROUP_ID", "-1003854308552")
    topic_id = getattr(settings, "TARGET_LEADS_TOPIC_ID", None) or os.getenv("TARGET_LEADS_TOPIC_ID", 1020)
    if not bot_token or not chat_id:
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
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": sos_text,
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
        if res.status_code == 200:
            _DISPATCHED_SOS.add(sos_key)
            logger.warning("[WATCHDOG SOS] Dispatched SOS alert for %s channel=%s", leadgen_id, channel)
            return True
    except Exception as exc:
        logger.error("[WATCHDOG SOS] Failed to dispatch SOS alert: %s", exc)
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


def audit_leadgen_health() -> Dict[str, Any]:
    """Perform a 3-system audit across Meta Graph API, AmoCRM, Sheets, and Telegram."""
    summary = get_delivery_summary(hours=24)
    meta_token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()

    meta_count = 0
    if meta_token:
        page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()
        version = os.getenv("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
        url = f"https://graph.facebook.com/{version}/{page_id}/leadgen_forms"
        try:
            r = requests.get(url, params={"access_token": meta_token, "fields": "id,leads_count"}, timeout=10)
            if r.status_code == 200:
                meta_count = sum(f.get("leads_count", 0) for f in r.json().get("data", []))
        except Exception:
            pass

    return {
        "meta_total_forms_leads": meta_count,
        "last_24h_total": summary["total"],
        "last_24h_amocrm": summary["amocrm_ok"],
        "last_24h_sheets": summary["sheets_ok"],
        "last_24h_telegram": summary["telegram_ok"],
        "pending_retries": summary["pending"],
        "status": "healthy" if summary["pending"] == 0 else "recovering",
    }
