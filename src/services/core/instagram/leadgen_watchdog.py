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


async def retry_pending_leadgen_deliveries() -> int:
    """Scan and retry any lead that failed AmoCRM, Sheets, or Telegram delivery."""
    pending = get_pending_deliveries(limit=20)
    if not pending:
        return 0

    from src.services.core.instagram.leadgen_router import (
        _notify_telegram,
        build_telegram_message,
        _fetch_leadgen_payload,
        flatten_field_data,
        _pick_name,
        _pick_phone,
        _pick_email,
        _amocrm_instance,
    )
    from src.services.core.instagram.leadgen_sheets import append_lead_to_sheet
    from src.services.core.crm.amocrm_pipeline_config import (
        TARGET_LEADS_PIPELINE_ID,
        TARGET_LEADS_FIRST_CONTACT_STATUS_ID,
    )

    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    recovered_count = 0

    for item in pending:
        leadgen_id = str(item["leadgen_id"])
        lead_id = item.get("lead_id")
        amocrm_ok = bool(item.get("amocrm_ok"))
        sheets_ok = bool(item.get("sheets_ok"))
        telegram_ok = bool(item.get("telegram_ok"))

        payload: Dict[str, Any] = {}
        if token:
            payload = await asyncio.to_thread(_fetch_leadgen_payload, leadgen_id, token)

        fields = flatten_field_data(payload.get("field_data") or [])
        name = _pick_name(fields) or "Mijoz"
        phone = _pick_phone(fields)
        email = _pick_email(fields)
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
                        pipeline_id=TARGET_LEADS_PIPELINE_ID,
                        status_id=TARGET_LEADS_FIRST_CONTACT_STATUS_ID,
                    )
                if lead_id:
                    mark_channel_delivered(leadgen_id, "amocrm")
                    amocrm_ok = True
                    logger.info("[WATCHDOG] AmoCRM recovered leadgen_id=%s amo_id=%s", leadgen_id, lead_id)
            except Exception as e:
                increment_delivery_retry(leadgen_id, f"amocrm_err: {e}")

        # 2. Retry Google Sheets
        if not sheets_ok:
            try:
                res = await asyncio.to_thread(append_lead_to_sheet, leadgen_id, lead_id, fields, form_name)
                if res:
                    mark_channel_delivered(leadgen_id, "sheets")
                    sheets_ok = True
                    logger.info("[WATCHDOG] Google Sheets recovered leadgen_id=%s", leadgen_id)
            except Exception as e:
                increment_delivery_retry(leadgen_id, f"sheets_err: {e}")

        # 3. Retry Telegram
        if not telegram_ok:
            try:
                msg = build_telegram_message(leadgen_id, lead_id, name, phone, email, fields)
                tg_res = await asyncio.to_thread(_notify_telegram, msg)
                if tg_res:
                    mark_channel_delivered(leadgen_id, "telegram")
                    telegram_ok = True
                    mark_leadgen_processed(leadgen_id, lead_id=lead_id)
                    logger.info("[WATCHDOG] Telegram alert recovered leadgen_id=%s", leadgen_id)
            except Exception as e:
                increment_delivery_retry(leadgen_id, f"telegram_err: {e}")

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
