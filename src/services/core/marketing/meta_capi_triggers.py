"""Meta CAPI triggerlari: AmoCRM status o'zgarishi va Telegram inline tugmalar.

Trigger A — `on_amo_status`: AmoCRM status -> Meta event (STATUS_EVENT_MAP).
Trigger B — `capi:q:<leadgen_id>` / `capi:p:<leadgen_id>` tugmalari; faqat
OWNER_ID / WHITELIST_IDS bosishi mumkin.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from src.services.core.marketing.meta_capi import is_enabled, send_crm_event
from src.services.core.tool_registry import ToolResult

logger = logging.getLogger(__name__)

STATUS_WON = 142
STATUS_LOST = 143
# 143 (yopildi) -> Disqualified ixtiyoriy: hozircha yuborilmaydi.
STATUS_EVENT_MAP: Dict[int, str] = {STATUS_WON: "Purchase"}
CALLBACK_PREFIX = "capi:"
CALLBACK_EVENTS = {"q": "QualifiedLead", "p": "Purchase"}
BUTTON_LABELS = {"q": "⭐ Sifatli lid", "p": "✅ Sotildi"}


def _qualified_status_ids() -> set[int]:
    """AmoCRM 'Sifatli'/'Uchrashuv' status ID'lari (vergul bilan, env)."""
    raw = os.getenv("META_CAPI_QUALIFIED_STATUS_IDS", "")
    return {int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()}


def event_for_status(status_id: Any) -> Optional[str]:
    try:
        sid = int(status_id)
    except (TypeError, ValueError):
        return None
    if sid in STATUS_EVENT_MAP:
        return STATUS_EVENT_MAP[sid]
    return "QualifiedLead" if sid in _qualified_status_ids() else None


async def on_amo_status(
    lead_id: int, status_id: Any, price: Optional[float] = None, leadgen_id: str = "",
) -> Optional[ToolResult]:
    """AmoCRM status o'zgarganda chaqiriladi. Lead Ads lidi bo'lmasa — None."""
    event_name = event_for_status(status_id)
    if not event_name or not is_enabled():
        return None
    if not leadgen_id:
        from src.services.core.instagram.leadgen_delivery import get_leadgen_id_by_lead_id
        leadgen_id = await asyncio.to_thread(get_leadgen_id_by_lead_id, int(lead_id)) or ""
    if not leadgen_id:
        return None
    return await send_crm_event(
        leadgen_id, event_name, amo_lead_id=int(lead_id), value=price, source="amocrm_status",
    )


def capi_button_rows(leadgen_id: str) -> List[List[Dict[str, str]]]:
    """Leadgen Telegram xabari uchun inline tugmalar (CAPI o'chiq bo'lsa — bo'sh)."""
    clean = str(leadgen_id or "").strip()
    if not clean or not is_enabled():
        return []
    return [[
        {"text": BUTTON_LABELS[k], "callback_data": f"{CALLBACK_PREFIX}{k}:{clean}"}
        for k in ("q", "p")
    ]]


def parse_callback(data: str) -> Optional[Tuple[str, str]]:
    """`capi:q:123` -> ("QualifiedLead", "123")."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "capi" or parts[1] not in CALLBACK_EVENTS:
        return None
    leadgen_id = parts[2].strip()
    if not leadgen_id.isdigit():
        return None
    return CALLBACK_EVENTS[parts[1]], leadgen_id


def is_capi_operator(user_id: Any) -> bool:
    from src.settings import settings
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    owner = int(getattr(settings, "OWNER_ID", 0) or 0)
    whitelist = {int(x) for x in (getattr(settings, "WHITELIST_IDS", None) or [])}
    return uid > 0 and (uid == owner or uid in whitelist)


async def handle_capi_callback(event: Any, data: str) -> None:
    """Telethon CallbackQuery handler (`capi:` prefiksi)."""
    parsed = parse_callback(data)
    if not parsed:
        await event.answer("⚠️ Noto'g'ri tugma.", alert=True)
        return
    if not is_capi_operator(event.sender_id):
        await event.answer("⚠️ Faqat ruxsat etilgan xodimlar belgilay oladi.", alert=True)
        return
    event_name, leadgen_id = parsed
    from src.services.core.instagram.leadgen_delivery import get_crm_checkpoint
    amo_lead_id = await asyncio.to_thread(get_crm_checkpoint, leadgen_id)
    result = await send_crm_event(
        leadgen_id, event_name, amo_lead_id=amo_lead_id, source=f"telegram:{event.sender_id}",
    )
    logger.info("[META CAPI] Tugma %s by %s -> %s", event_name, event.sender_id, result.status)
    await _answer_result(event, event_name, result)


async def _answer_result(event: Any, event_name: str, result: ToolResult) -> None:
    label = "⭐ Sifatli lid" if event_name == "QualifiedLead" else "✅ Sotildi"
    if result.status == "sent":
        await event.answer(f"{label} — Meta'ga yuborildi.")
        try:
            # `.text` — mijoz parse_mode'ida formatlangan; reply_markup saqlanadi.
            msg = event.message
            await event.edit(f"{msg.text}\n\n{label} — Meta CAPI ✔", buttons=msg.reply_markup)
        except Exception:
            logger.debug("[META CAPI] Xabarni tahrirlab bo'lmadi")
    elif result.status == "duplicate":
        await event.answer(f"{label} allaqachon yuborilgan.")
    elif result.status == "disabled":
        await event.answer("⚠️ Meta CAPI o'chirilgan.", alert=True)
    else:
        await event.answer("❌ Meta'ga yuborib bo'lmadi, keyinroq qayta bosing.", alert=True)
