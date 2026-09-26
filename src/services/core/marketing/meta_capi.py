"""Meta Conversions API — CRM (Conversion Leads) eventlari.

Lead Ads lidining keyingi taqdirini (QualifiedLead / Purchase) Meta dataset'iga
qaytaradi: `POST graph.facebook.com/{version}/{dataset_id}/events`.
`META_CAPI_ENABLED=False` (default) bo'lsa hech narsa yuborilmaydi.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests

from src.services.core.marketing import meta_capi_store as store
from src.services.core.tool_registry import ToolResult

logger = logging.getLogger(__name__)

TOOL_NAME = "meta_capi"
SUPPORTED_EVENTS = {"Lead", "QualifiedLead", "Purchase", "Disqualified"}
LEAD_EVENT_SOURCE = "Oisha-OS"
_RETRIES = 3
_BACKOFF_SEC = 1.0


def _secret(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _config() -> Dict[str, Any]:
    from src.settings import settings
    return {
        "enabled": bool(getattr(settings, "META_CAPI_ENABLED", False)),
        "dataset_id": str(getattr(settings, "META_CAPI_DATASET_ID", None) or "").strip(),
        "token": _secret(getattr(settings, "META_CAPI_ACCESS_TOKEN", None)),
        "test_code": str(getattr(settings, "META_CAPI_TEST_EVENT_CODE", None) or "").strip(),
        "version": os.getenv("META_CAPI_GRAPH_VERSION", "v21.0").strip() or "v21.0",
    }


def is_enabled() -> bool:
    cfg = _config()
    return bool(cfg["enabled"] and cfg["dataset_id"] and cfg["token"])


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return _sha256(digits) if digits else ""


def hash_email(email: str) -> str:
    clean = (email or "").strip().lower()
    return _sha256(clean) if clean else ""


def build_event(
    leadgen_id: str, event_name: str, value: Optional[float] = None, currency: str = "UZS",
    phone: str = "", email: str = "", event_time: Optional[int] = None,
) -> Dict[str, Any]:
    """Meta CRM event payload (bitta event)."""
    user_data: Dict[str, Any] = {"lead_id": str(leadgen_id)}
    if phone and hash_phone(phone):
        user_data["ph"] = [hash_phone(phone)]
    if email and hash_email(email):
        user_data["em"] = [hash_email(email)]
    custom_data: Dict[str, Any] = {"event_source": "crm", "lead_event_source": LEAD_EVENT_SOURCE}
    if event_name == "Purchase":
        custom_data["value"] = float(value or 0)
        custom_data["currency"] = currency
    return {
        "event_name": event_name,
        # Deterministik ID: tarmoq xatosidan keyingi retry Meta'da dublikat bo'lmaydi.
        "event_id": f"crm-{leadgen_id}-{event_name}",
        "event_time": int(event_time or time.time()),
        "action_source": "system_generated",
        "user_data": user_data,
        "custom_data": custom_data,
    }


def _post_events(cfg: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://graph.facebook.com/{cfg['version']}/{cfg['dataset_id']}/events"
    body: Dict[str, Any] = {"data": [event], "access_token": cfg["token"]}
    if cfg["test_code"]:
        body["test_event_code"] = cfg["test_code"]
    last_error = ""
    for attempt in range(_RETRIES):
        try:
            res = requests.post(url, json=body, timeout=15)
            if res.status_code == 200:
                return {"ok": True, "response": res.json()}
            last_error = f"HTTP {res.status_code}"
            if 400 <= res.status_code < 500 and res.status_code != 429:
                break  # validatsiya xatosi — qayta urinish foydasiz
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        if attempt < _RETRIES - 1:
            time.sleep(_BACKOFF_SEC * (2 ** attempt))
    return {"ok": False, "error": last_error}


async def send_crm_event(
    leadgen_id: str, event_name: str, amo_lead_id: Optional[int] = None,
    value: Optional[float] = None, phone: str = "", email: str = "", source: str = "",
) -> ToolResult:
    """Bitta CRM eventini idempotent yuboradi."""
    leadgen_id = str(leadgen_id or "").strip()
    meta = {"leadgen_id": leadgen_id, "event_name": event_name, "source": source}
    if event_name not in SUPPORTED_EVENTS or not leadgen_id:
        return ToolResult(TOOL_NAME, False, status="invalid", reason="bad_event", metadata=meta)
    if not is_enabled():
        return ToolResult(TOOL_NAME, False, status="disabled", reason="capi_disabled", metadata=meta)
    if not await store.claim_event(leadgen_id, event_name, amo_lead_id, source):
        return ToolResult(TOOL_NAME, True, status="duplicate", reason="already_sent", metadata=meta)

    event = build_event(leadgen_id, event_name, value=value, phone=phone, email=email)
    result = await asyncio.to_thread(_post_events, _config(), event)
    await store.mark_result(leadgen_id, event_name, result["ok"], result.get("error", ""))
    if result["ok"]:
        logger.info("[META CAPI] %s yuborildi: leadgen_id=%s (%s)", event_name, leadgen_id, source)
        return ToolResult(TOOL_NAME, True, status="sent", sent_count=1, metadata=meta,
                          raw=result.get("response") or {})
    logger.warning("[META CAPI] %s xato: leadgen_id=%s %s", event_name, leadgen_id, result.get("error"))
    return ToolResult(TOOL_NAME, False, status="failed", reason=result.get("error"), metadata=meta)
