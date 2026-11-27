"""Sotuv guruhida kontakt/lid ulashilganda sotuv menejerini biriktirish handleri.

Aiogram kuzatuvchi middleware kontakt kartalari va telefonli xabarlarni vaqtincha
xotirada saqlaydi; rahbar lidni topshirishni soʻraganda ``group_lead_crm`` orqali
amoCRMʼda biriktirib guruhga javob beradi.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.handlers.group_lead_crm import (
    compute_due_timestamp,
    execute_group_lead_assignment,
    select_seller_for_lead,
)

logger = logging.getLogger("OishaGroupLeadAssign")

CACHE_TTL_SECONDS = 1800
_PHONE_RE = re.compile(r"(?:\+?998[\s\-\(\)]*\d{2}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}|\b\d{9}\b)")
_SLASH_CMD_RE = re.compile(r"^/\w+(?:@\w+)?\s*")
_ASSIGN_TRIGGER_RE = re.compile(
    r"(?is)("
    r"^/(?:lid_topshir|assign_lead)(?:@\w+)?\b"
    r"|qaysi\s+(?:sotuv\s+)?menejer\w*\s+olad"
    r"|sotuv\s+menejer\w*.*?(?:belgila|biriktir|topshir|ber)"
    r"|(?:lead|lid|sdelka)\w*\s+(?:topshir|biriktir|taqsimla)"
    r"|kimga\s+(?:biriktir|topshir)\w*"
    r")"
)
_LEADING_OTHER_BOT_RE = re.compile(
    r"^\s*@?(?:amin[aа]|амин[aа]|amina_binti_sabot|mr\.?\s?jon|mrjon|jon_clawbot)\b",
    re.IGNORECASE,
)
_SELF_CALL_RE = re.compile(r"(?i)(?<![\w@])(?:@?jonairobot|oisha|oyisha|оиша)\b")


@dataclass(frozen=True)
class CachedContact:
    phone: str
    name: str
    ts: float
    extra_text: str = ""


class GroupLeadContextCache:
    """Guruhda ulashilgan oxirgi kontakt va telefonli xabarlarni vaqtincha saqlaydi."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._by_chat: Dict[int, List[CachedContact]] = {}

    def remember(
        self, chat_id: int, phone: str, name: str, *, now: Optional[float] = None, extra_text: str = ""
    ) -> None:
        norm = normalize_uz_phone(phone)
        if not norm:
            return
        ts = time.monotonic() if now is None else now
        bucket = [c for c in self._by_chat.get(chat_id, []) if ts - c.ts <= self._ttl and c.phone != norm]
        bucket.append(CachedContact(phone=norm, name=(name or "").strip() or norm, ts=ts, extra_text=extra_text))
        self._by_chat[chat_id] = bucket[-10:]

    def latest(self, chat_id: int, *, now: Optional[float] = None) -> Optional[CachedContact]:
        ts = time.monotonic() if now is None else now
        bucket = [c for c in self._by_chat.get(chat_id, []) if ts - c.ts <= self._ttl]
        self._by_chat[chat_id] = bucket
        return bucket[-1] if bucket else None


def normalize_uz_phone(raw: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    return None


def extract_contact_from_message(message: Any) -> Optional[Tuple[str, str]]:
    """Aiogram message obyektidan (phone, display_name) ajratib oladi."""
    contact = getattr(message, "contact", None)
    if contact is not None:
        phone = normalize_uz_phone(getattr(contact, "phone_number", None))
        if phone:
            parts = [getattr(contact, "first_name", "") or "", getattr(contact, "last_name", "") or ""]
            name = " ".join(p.strip() for p in parts if p and p.strip()) or phone
            return phone, name

    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    match = _PHONE_RE.search(text)
    if not match:
        return None
    phone = normalize_uz_phone(match.group(0))
    if not phone:
        return None
    cleaned = _SLASH_CMD_RE.sub("", text).strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    first_line = re.sub(_PHONE_RE, "", lines[0]).strip(" -—:|,") if lines else ""
    if first_line and not first_line.startswith("/") and len(first_line) <= 60:
        return phone, first_line
    return phone, phone


def allowed_sales_group_ids(settings_obj: Any = None) -> set[int]:
    if settings_obj is None:
        from src.settings import settings as settings_obj
    candidates = (
        getattr(settings_obj, "CRM_GROUP_ID", None),
        getattr(settings_obj, "TEAM_GROUP_ID", None),
        getattr(settings_obj, "TARGET_LEADS_GROUP_ID", None),
        getattr(settings_obj, "CRM_SALES_REPORT_GROUP_ID", None),
    )
    return {int(cid) for cid in candidates if cid is not None}


def is_group_lead_assign_request(text: str) -> bool:
    clean = (text or "").strip()
    if not clean:
        return False
    if _LEADING_OTHER_BOT_RE.search(clean) and not _SELF_CALL_RE.search(clean):
        return False
    return bool(_ASSIGN_TRIGGER_RE.search(clean))


def _observe_contact_if_group(
    event: Any, ctx_cache: GroupLeadContextCache, group_ids_getter: Callable[[], set[int]]
) -> None:
    chat = getattr(event, "chat", None)
    user = getattr(event, "from_user", None)
    if chat is None or user is None or getattr(user, "is_bot", False):
        return
    if int(getattr(chat, "id", 0) or 0) not in group_ids_getter():
        return
    extracted = extract_contact_from_message(event)
    if extracted:
        txt = getattr(event, "text", None) or getattr(event, "caption", None) or ""
        ctx_cache.remember(int(chat.id), extracted[0], extracted[1], extra_text=txt)


def _resolve_target_contact(
    message: Any, ctx_cache: GroupLeadContextCache
) -> Tuple[Optional[Tuple[str, str]], str]:
    resolved = extract_contact_from_message(message)
    reply = getattr(message, "reply_to_message", None)
    reply_text = (getattr(reply, "text", None) or getattr(reply, "caption", None) or "").strip() if reply else ""
    if resolved is None and reply is not None:
        resolved = extract_contact_from_message(reply)
    cached = ctx_cache.latest(int(message.chat.id))
    if resolved is None and cached is not None:
        resolved = (cached.phone, cached.name)
    extra_parts = [reply_text] if reply_text else []
    if cached and resolved and cached.phone == resolved[0] and cached.extra_text:
        extra_parts.append(cached.extra_text)
    return resolved, "\n".join(extra_parts).strip()


async def _dispatch_assign_message(
    message: Any,
    *,
    ctx_cache: GroupLeadContextCache,
    get_amocrm_client: Optional[Callable[[], Any]],
) -> None:
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    resolved, contact_context = _resolve_target_contact(message, ctx_cache)
    if resolved is None:
        await message.reply(
            "Lidni biriktirish uchun mijoz kontaktini yoki telefon raqamini (+998...) yuboring "
            "yoxud kontakt xabariga reply qiling.",
            parse_mode=None,
        )
        return
    amocrm = get_amocrm_client() if get_amocrm_client else None
    if amocrm is None:
        await message.reply("❌ amoCRM ulanmagan.", parse_mode=None)
        return
    reply_html = await execute_group_lead_assignment(
        amocrm=amocrm,
        phone=resolved[0],
        contact_name=resolved[1],
        instruction_text=text,
        contact_context=contact_context,
    )
    await message.reply(reply_html, parse_mode="HTML", disable_web_page_preview=True)


def register_group_lead_assign_handlers(
    dispatcher: Any,
    *,
    is_admin: Callable[[int], bool],
    get_amocrm_client: Optional[Callable[[], Any]],
    cache: Optional[GroupLeadContextCache] = None,
    group_ids_getter: Callable[[], set[int]] = allowed_sales_group_ids,
) -> GroupLeadContextCache:
    """Aiogram dispatcherʼga kontakt kuzatuvchi va lid biriktiruvchi handlerni ulaydi."""
    ctx_cache = cache or GroupLeadContextCache()
    msg_router = getattr(dispatcher, "message", None)
    if msg_router is None:
        return ctx_cache

    async def _observer(handler: Any, event: Any, data: dict) -> Any:
        _observe_contact_if_group(event, ctx_cache, group_ids_getter)
        return await handler(event, data)

    async def _matches(message: Any) -> bool:
        chat = getattr(message, "chat", None)
        user = getattr(message, "from_user", None)
        if chat is None or user is None or getattr(user, "is_bot", False):
            return False
        if int(getattr(chat, "id", 0) or 0) not in group_ids_getter():
            return False
        if not is_admin(int(getattr(user, "id", 0) or 0)):
            return False
        return is_group_lead_assign_request(getattr(message, "text", None) or getattr(message, "caption", None) or "")

    async def _handle(message: Any) -> None:
        await _dispatch_assign_message(message, ctx_cache=ctx_cache, get_amocrm_client=get_amocrm_client)

    msg_router.outer_middleware.register(_observer)
    msg_router.register(_handle, _matches)
    logger.info("[GROUP-ASSIGN] Sotuv guruhi lid-biriktirish handleri ulandi.")
    return ctx_cache


__all__ = [
    "CachedContact",
    "GroupLeadContextCache",
    "allowed_sales_group_ids",
    "compute_due_timestamp",
    "execute_group_lead_assignment",
    "extract_contact_from_message",
    "is_group_lead_assign_request",
    "normalize_uz_phone",
    "register_group_lead_assign_handlers",
    "select_seller_for_lead",
]
