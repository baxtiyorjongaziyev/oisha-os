"""Facebook Lead Ads webhook routing to AmoCRM."""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, Iterable, Optional

import requests
import structlog

from src.settings import settings
from src.services.core.crm.amocrm_pipeline_config import (
    UTC_PIPELINE_ID,
    UTC_NEW_STATUS_ID,
    TARGET_LEADS_INHOUSE_PIPELINE_ID,
    TARGET_LEADS_INHOUSE_NEW_STATUS_ID,
    TARGET_LEADS_PIPELINE_ID,
    TARGET_LEADS_FIRST_CONTACT_STATUS_ID,
)
from src.services.core.instagram.graph_client import InstagramGraphClient
from src.services.core.instagram.leadgen_formatter import (
    clean_form_key,
    humanize_question,
    humanize_answer,
    build_leadgen_note as _fmt_build_note,
    build_telegram_message as _fmt_build_tg,
)
from src.services.core.instagram.leadgen_custom_fields import extract_lead_custom_fields
from src.services.core.instagram.leadgen_dedup import is_leadgen_processed, mark_leadgen_processed
from src.services.core.instagram.leadgen_sheets import append_lead_to_sheet
from src.services.core.instagram.leadgen_delivery import (
    _ROUTING_LOCK,
    get_crm_checkpoint,
    save_crm_checkpoint,
    record_delivery_status,
    get_delivery_channel_status,
    get_lead_destination,
    get_next_lead_destination,
)
from src.services.core.marketing.ad_name_resolver import resolve_ad_name
from src.services.core.marketing.attribution_store import save_attribution
from src.services.core.marketing.lead_cost_estimator import estimate_cost_per_lead
from src.time_utils import get_local_now

logger = structlog.get_logger("MetaLeadgenRouter")

NAME_KEYS = {
    "full_name", "name", "first_name", "last_name", "ismingizni_yozing",
    "ismingiz_nima", "ismingiz", "ism", "fio", "mijoz_ismi", "client_name", "your_name",
}
PHONE_KEYS = {
    "phone", "phone_number", "telefon", "tel", "mobile_phone",
    "telefon_raqamingizni_kiriting", "telefon_raqamingizni_yozing", "telefon_raqam",
    "telefon_raqamingiz", "telefon_raqamingz", "what_is_your_phone_number", "aloqa_uchun_telefon",
}
EMAIL_KEYS = {"email", "email_address", "e_mail", "pochta", "elektron_pochta"}


def _clean_key(value: str) -> str:
    return clean_form_key(value)


def _field_value(item: Dict[str, Any]) -> str:
    values = item.get("values")
    if isinstance(values, list):
        return ", ".join(str(v).strip() for v in values if str(v).strip())
    value = item.get("value")
    return str(value).strip() if value is not None else ""


def flatten_field_data(field_data: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """Convert Meta field_data[] into a simple key/value mapping."""
    fields: Dict[str, str] = {}
    for item in field_data or []:
        if not isinstance(item, dict):
            continue
        key = _clean_key(str(item.get("name") or ""))
        value = _field_value(item)
        if key and value:
            fields[key] = value
    return fields


def _is_name_field(key: str) -> bool:
    cleaned = _clean_key(key)
    if cleaned in NAME_KEYS:
        return True
    if any(w in cleaned for w in ("brend", "biznes", "brand", "company", "kompaniya", "nomi")):
        return False
    parts = cleaned.split("_")
    return "ism" in parts or "ismingiz" in parts or "fio" in parts or cleaned.startswith("ism")


def _is_phone_field(key: str) -> bool:
    cleaned = _clean_key(key)
    return cleaned in PHONE_KEYS or any(p in ("phone", "tel", "telefon") for p in cleaned.split("_"))


def _is_email_field(key: str) -> bool:
    cleaned = _clean_key(key)
    return cleaned in EMAIL_KEYS or any(p in ("email", "mail", "pochta") for p in cleaned.split("_"))


def _pick_name(fields: Dict[str, str]) -> str:
    for key in ("ismingizni_yozing", "ismingiz", "ism", "full_name", "name", "first_name", "fio", "client_name"):
        if fields.get(key) and fields[key].strip():
            return fields[key].strip()
    for key, val in fields.items():
        if _is_name_field(key) and val and val.strip():
            return val.strip()
    return ""


def _pick_phone(fields: Dict[str, str]) -> str:
    for key in ("phone", "phone_number", "mobile_phone", "telefon_raqamingizni_kiriting", "telefon_raqam", "telefon"):
        val = fields.get(key)
        if val and len(re.sub(r"\D", "", val)) >= 7:
            return val.strip()
    for key, val in fields.items():
        if _is_phone_field(key) and val and len(re.sub(r"\D", "", val)) >= 7:
            return val.strip()
    return fields.get("phone") or fields.get("phone_number") or ""


def _pick(fields: Dict[str, str], keys: set[str]) -> str:
    for key in keys:
        if fields.get(key):
            return fields[key]
    for key, value in fields.items():
        if key in keys or any(part in keys for part in key.split("_")):
            return value
    return ""


def _excluded_leadgen_keys(fields: Dict[str, str]) -> set[str]:
    return {k for k in fields if _is_name_field(k) or _is_phone_field(k) or _is_email_field(k)}


def build_leadgen_note(
    leadgen_id: str, payload: Dict[str, Any], fields: Dict[str, str], ad_name: Optional[str] = None,
) -> str:
    """Format leadgen note using leadgen_formatter with excluded contact keys."""
    return _fmt_build_note(leadgen_id, payload, fields, _excluded_leadgen_keys(fields), ad_name=ad_name)


def build_telegram_message(
    leadgen_id: str, lead_id: Optional[int], name: str, phone: str, email: str,
    fields: Dict[str, str], cost_per_lead: Optional[float] = None, ad_name: Optional[str] = None,
) -> str:
    """Format clean Telegram alert using leadgen_formatter."""
    return _fmt_build_tg(
        leadgen_id, lead_id, name, phone, email, fields,
        _excluded_leadgen_keys(fields), cost_per_lead=cost_per_lead, ad_name=ad_name,
    )


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _notify_telegram(text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    chat_id = getattr(settings, "TARGET_LEADS_GROUP_ID", None) or os.getenv("TARGET_LEADS_GROUP_ID")
    bot_token = _secret_text(getattr(settings, "BOT_TOKEN", None)) or os.getenv("BOT_TOKEN", "").strip()
    if not chat_id or not bot_token:
        logger.warning("[META LEADGEN] Telegram notification skipped: missing config")
        return False

    payload: Dict[str, Any] = {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
    }
    topic_id = getattr(settings, "TARGET_LEADS_TOPIC_ID", None) or os.getenv("TARGET_LEADS_TOPIC_ID")
    if topic_id is not None:
        payload["message_thread_id"] = topic_id
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload, timeout=10)
        return res.status_code == 200
    except requests.RequestException as exc:
        logger.warning("[META LEADGEN] Telegram notification failed", error=type(exc).__name__)
        return False


def _fetch_leadgen_payload(leadgen_id: str, token: str) -> Dict[str, Any]:
    api_version = os.environ.get("META_GRAPH_API_VERSION", "").strip() or "v19.0"
    url = f"https://graph.facebook.com/{api_version}/{leadgen_id}"
    params = {
        "fields": "created_time,field_data,form_id,ad_id",
        "access_token": token,
    }
    response = requests.get(url, params=params, timeout=15)
    if response.status_code >= 400:
        logger.warning("[META LEADGEN] Graph fetch failed", status=response.status_code)
        return {}
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _amocrm_instance() -> Any:
    try:
        from src.api.routes.state import api_state
        if api_state.amocrm_instance:
            return api_state.amocrm_instance
    except Exception:
        pass

    from src.services.core.crm.amocrm.sync import AmoCRMSync
    return AmoCRMSync()


async def route_leadgen_event(value: Dict[str, Any], access_token: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    async with _ROUTING_LOCK:
        return await _route_leadgen_event(value, access_token, force)


async def _route_leadgen_event(value: Dict[str, Any], access_token: Optional[str], force: bool) -> Dict[str, Any]:
    """Fetch a Facebook Lead Ads submission and create/update an AmoCRM lead."""
    leadgen_id = str(value.get("leadgen_id") or value.get("lead_id") or "").strip()
    if not leadgen_id:
        return {"ok": False, "reason": "missing_leadgen_id"}

    if not force and is_leadgen_processed(leadgen_id):
        logger.info("[META LEADGEN] Lead already processed, skipping duplicate", leadgen_id=leadgen_id)
        return {"ok": True, "leadgen_id": leadgen_id, "skipped": True}

    token = access_token or InstagramGraphClient().access_token
    if not token:
        return {"ok": False, "reason": "missing_meta_token"}

    payload = value if value.get("field_data") else {}
    if not payload:
        payload = await asyncio.to_thread(_fetch_leadgen_payload, leadgen_id, token)
    fields = flatten_field_data(payload.get("field_data") or [])
    if not fields:
        return {"ok": False, "reason": "missing_field_data", "leadgen_id": leadgen_id}
    name = _pick_name(fields) or "Facebook Lead Ads"
    phone = _pick_phone(fields)
    email = _pick(fields, EMAIL_KEYS)

    merged_payload = {**value, **payload}
    ad_id = str(merged_payload.get("ad_id") or "")
    ad_name = await asyncio.to_thread(resolve_ad_name, ad_id)

    note = build_leadgen_note(leadgen_id, merged_payload, fields, ad_name=ad_name)

    custom_fields = extract_lead_custom_fields(fields)
    amocrm = _amocrm_instance()
    deal_name = f"{name} | 🎬 {ad_name}" if ad_name else name

    destination = await asyncio.to_thread(get_lead_destination, leadgen_id)
    if not destination:
        destination = await asyncio.to_thread(get_next_lead_destination)

    if destination == "inhouse":
        target_pipeline_id = TARGET_LEADS_INHOUSE_PIPELINE_ID
        target_status_id = TARGET_LEADS_INHOUSE_NEW_STATUS_ID
        dest_tag = "inhouse"
        dest_label = "🏠 Inhouse (Jon Branding)"
    else:
        target_pipeline_id = UTC_PIPELINE_ID
        target_status_id = UTC_NEW_STATUS_ID
        dest_tag = "utc_outsource"
        dest_label = "🌐 UTC Outsource"

    checkpoint = None if force else await asyncio.to_thread(get_crm_checkpoint, leadgen_id)
    if checkpoint:
        lead_id = checkpoint
    elif phone:
        lead_id = await amocrm.ensure_lead(
            name=deal_name,
            phone=phone,
            note=note,
            pipeline_id=target_pipeline_id,
            status_id=target_status_id,
            custom_fields=custom_fields,
        )
    else:
        lead_id = await amocrm.create_standalone_lead(
            name=deal_name,
            pipeline_id=target_pipeline_id,
            status_id=target_status_id,
            tags=["Facebook Lead Ads", "Oisha", f"taqsimot:{dest_tag}"],
            note=note,
            custom_fields=custom_fields,
        )

    if not lead_id:
        return {"ok": False, "reason": "crm_delivery_failed", "leadgen_id": leadgen_id}

    await asyncio.to_thread(
        save_attribution,
        leadgen_id,
        int(lead_id),
        str(merged_payload.get("campaign_id") or ""),
        str(merged_payload.get("campaign_name") or ""),
        str(merged_payload.get("ad_id") or ""),
        str(merged_payload.get("form_id") or ""),
        get_local_now().isoformat(),
    )

    if not checkpoint:
        await asyncio.to_thread(save_crm_checkpoint, leadgen_id, int(lead_id), destination=destination)
        await amocrm.update_lead_status(
            int(lead_id),
            target_status_id,
            pipeline_id=target_pipeline_id,
        )
        tags = ["Facebook Lead Ads", "Oisha", f"taqsimot:{dest_tag}"]
        if ad_name:
            tags.append(f"reklama:{ad_name.lower()}")
        for t in tags:
            await amocrm.add_lead_tag(int(lead_id), t)

    from src.services.core.marketing.meta_ads_client import MetaAdsClient, get_creative_url
    creative_url = None
    if ad_id:
        meta_ads = MetaAdsClient()
        creative_url = await asyncio.to_thread(meta_ads.get_ad_creative_url, str(ad_id))
    if not creative_url and ad_name:
        creative_url = get_creative_url(ad_name)

    if not checkpoint:
        if email:
            await asyncio.to_thread(amocrm.add_lead_note, int(lead_id), f"Email: {email}")
        if creative_url:
            await asyncio.to_thread(amocrm.add_lead_note, int(lead_id), f"🎬 Reklama videosi: {creative_url}")

    campaign_id = str(merged_payload.get("campaign_id") or "")
    cost_per_lead = await asyncio.to_thread(estimate_cost_per_lead, campaign_id)
    ch_status = {} if (force or not checkpoint) else await asyncio.to_thread(get_delivery_channel_status, leadgen_id)

    telegram_ok = bool(ch_status.get("telegram"))
    if not telegram_ok or force:
        telegram_text = build_telegram_message(
            leadgen_id, lead_id, name, phone, email, fields,
            cost_per_lead=cost_per_lead, ad_name=ad_name,
        )
        telegram_text += f"\n\n🏢 <b>Taqsimot:</b> {dest_label}"
        buttons = []
        if creative_url:
            buttons.append({"text": f"🎬 {ad_name or 'Kreativ'}ni ko'rish", "url": creative_url})
        if lead_id:
            buttons.append({"text": "🧾 AmoCRM bitimi", "url": f"https://jonbranding.amocrm.ru/leads/detail/{lead_id}"})
        reply_markup = {"inline_keyboard": [buttons]} if buttons else None
        telegram_ok = await asyncio.to_thread(_notify_telegram, telegram_text, reply_markup=reply_markup)

    sheets_ok = bool(ch_status.get("sheets"))
    if not sheets_ok or force:
        form_title = str(merged_payload.get("form_name") or merged_payload.get("form_id") or "")
        sheets_ok = await asyncio.to_thread(
            append_lead_to_sheet,
            leadgen_id, int(lead_id) if lead_id else None, fields, form_title,
            ad_name=ad_name, creative_url=creative_url, destination=destination,
        )

    await asyncio.to_thread(
        record_delivery_status,
        leadgen_id, int(lead_id) if lead_id else None,
        bool(lead_id), bool(sheets_ok), bool(telegram_ok),
        destination=destination,
    )
    if telegram_ok and sheets_ok and lead_id:
        mark_leadgen_processed(leadgen_id, lead_id=int(lead_id))

    logger.info(
        "[META LEADGEN] Routed Facebook lead",
        leadgen_id=leadgen_id,
        lead_id=lead_id,
        destination=destination,
        sheets_ok=bool(sheets_ok),
        tg_ok=bool(telegram_ok),
    )
    return {
        "ok": bool(lead_id) and telegram_ok and bool(sheets_ok),
        "lead_id": lead_id,
        "leadgen_id": leadgen_id,
        "destination": destination,
        "telegram_notified": telegram_ok,
        "sheets_appended": bool(sheets_ok),
    }
