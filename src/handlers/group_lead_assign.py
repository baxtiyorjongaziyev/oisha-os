"""Sotuv guruhida kontakt/lid ulashilganda sotuv menejerini biriktirish handleri.

Owner guruhga kontakt kartasi yoki telefon raqam tashlab:
- "Qaysi sotuv menejeri oladi?"
- "Sotuv menejerini belgilab leadni topshir, darsdan keyin aloqaga chiqish kerak"
deb yozsa, Oisha (@jonairobot) lidni amoCRMʼda topadi yoki ochadi, qoida boʻyicha
sotuv menejeriga (TN/networking -> Shahnoza; yangi lid -> eng kam yuklamali Closer:
Rayxona / Mumtozmaxal) biriktiradi, izoh + vazifa yaratadi va guruhda tasdiqlaydi.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
)
from src.services.core.crm.lead_owner_resolver import _tag_names, owners_from_tags
from src.services.core.crm.team_roster import StaffMember, find_staff
from src.time_utils import get_local_now

logger = logging.getLogger("OishaGroupLeadAssign")

CACHE_TTL_SECONDS = 1800
_PHONE_RE = re.compile(r"(?:\+?998[\s\-\(\)]*\d{2}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}|\b\d{9}\b)")
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
    r"^\s*@?(?:amina|амина|amina_binti_sabot|mr\.?\s?jon|mrjon|jon_clawbot)\b",
    re.IGNORECASE,
)
_SELF_CALL_RE = re.compile(r"(?i)(?<![\w@])(?:@?jonairobot|oisha|oyisha|оиша)\b")
_NETWORKING_RE = re.compile(
    r"(?i)(?:\btn\s*\d*\b|\bt/n\s*\d*\b|tez\s+natija|networking|trening|tanishuv|klub)"
)
_AFTER_CLASS_RE = re.compile(r"(?i)(?:darsdan\s+keyin|kechqurun|18\s*:\s*30|18\s*:\s*00)")

_LIVE_TG_HANDLES: Dict[str, str] = {
    "shahnoza": "@jonbranding_assistant",
    "rayxona": "@RayxonMenejer",
    "mumtozmaxal": "@MumtozmaxalJonbranding",
}


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

    def remember(self, chat_id: int, phone: str, name: str, *, now: Optional[float] = None, extra_text: str = "") -> None:
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
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first_line = re.sub(_PHONE_RE, "", lines[0]).strip(" -—:|,") if lines else ""
    return phone, (first_line[:60] if first_line and len(first_line) <= 60 else phone)


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


def _explicit_seller_from_text(text: str) -> Optional[StaffMember]:
    lowered = (text or "").lower()
    patterns = (
        ("shahnoza", r"\b(?:shahnoza|shaxnoza|jonbranding_assistant)\w*"),
        ("rayxona", r"\b(?:rayxona|rayxon|rayhona|rayxonmenejer|rayxonjonbranding)\w*"),
        ("mumtozmaxal", r"\b(?:mumtozmaxal|mumtozmahal|mumtoz|mumtozmaxaljonbranding)\w*"),
    )
    for slug, pat in patterns:
        if re.search(pat, lowered):
            return find_staff(slug)
    return None


async def select_seller_for_lead(context_blob: str, amocrm: Any = None) -> Tuple[StaffMember, str]:
    """Qoida va joriy amoCRM yuklamasiga qarab sotuv menejerini tanlaydi."""
    explicit = _explicit_seller_from_text(context_blob)
    if explicit is not None:
        return explicit, "rahbar koʻrsatmasi"

    if _NETWORKING_RE.search(context_blob or ""):
        shahnoza = find_staff("shahnoza")
        if shahnoza is not None:
            return shahnoza, "TN / networking qoidasi"

    loads: Dict[str, int] = {"Rayxona": 0, "Mumtozmaxal": 0}
    if amocrm is not None and hasattr(amocrm, "get_leads"):
        try:
            leads = await amocrm.get_leads(
                limit=250,
                **{"filter[pipeline_id][]": SALES_PIPELINE_ID, "order[created_at]": "desc"},
            )
            for item in leads or []:
                if item.get("status_id") in (142, 143):
                    continue
                for owner in owners_from_tags(_tag_names(item)):
                    if owner in loads:
                        loads[owner] += 1
        except Exception as exc:
            logger.warning("[GROUP-ASSIGN] Yuklama oʻqilmadi, default tartib ishlatiladi: %s", exc)

    chosen_slug = "rayxona" if loads["Rayxona"] <= loads["Mumtozmaxal"] else "mumtozmaxal"
    chosen = find_staff(chosen_slug) or find_staff("shahnoza")
    if chosen is None:
        raise RuntimeError("Faol sotuv menejeri topilmadi")
    return chosen, f"Closer navbati (aktiv lidlar: Rayxona={loads['Rayxona']}, Mumtozmaxal={loads['Mumtozmaxal']})"


def compute_due_timestamp(instruction_text: str, now: Optional[datetime] = None) -> Tuple[int, str]:
    cur = now or get_local_now()
    if _AFTER_CLASS_RE.search(instruction_text or ""):
        target = cur.replace(hour=18, minute=30, second=0, microsecond=0)
        if target <= cur:
            target = (cur + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        return int(target.timestamp()), target.strftime("%d.%m %H:%M")
    target = cur + timedelta(hours=2)
    return int(target.timestamp()), target.strftime("%d.%m %H:%M")


async def _find_or_open_lead(amocrm: Any, phone: str, title: str, note: str) -> Optional[int]:
    existing = None
    if hasattr(amocrm, "find_active_lead_by_phone"):
        fn = amocrm.find_active_lead_by_phone
        existing = await fn(phone) if asyncio.iscoroutinefunction(fn) else await asyncio.to_thread(fn, phone)
    if existing and existing.get("id"):
        return int(existing["id"])
    if hasattr(amocrm, "ensure_lead"):
        created = await amocrm.ensure_lead(
            name=title,
            phone=phone,
            note=note,
            pipeline_id=SALES_PIPELINE_ID,
            status_id=SALES_NEW_STATUS_ID,
        )
        return int(created) if created else None
    return None


async def _patch_generic_lead_title(amocrm: Any, lead_id: int, desired_title: str) -> None:
    if not hasattr(amocrm, "get_lead") or not hasattr(amocrm, "_get_headers"):
        return
    try:
        import requests

        lead = await amocrm.get_lead(lead_id)
        cur_name = str((lead or {}).get("name") or "").strip()
        if not cur_name or cur_name.startswith(("Сделка #", "DM Lead:")):
            url = f"{amocrm.base_url}/api/v4/leads/{lead_id}"
            await asyncio.to_thread(
                requests.patch,
                url,
                headers=amocrm._get_headers(),
                json={"name": desired_title},
                timeout=20,
            )
    except Exception as exc:
        logger.debug("[GROUP-ASSIGN] Lead nomi yangilanmadi (%s): %s", lead_id, exc)


async def execute_group_lead_assignment(
    *,
    amocrm: Any,
    phone: str,
    contact_name: str,
    instruction_text: str,
    now: Optional[datetime] = None,
) -> str:
    context_blob = f"{contact_name}\n{instruction_text}".strip()
    seller, reason = await select_seller_for_lead(context_blob, amocrm=amocrm)
    seller_short = seller.name.split()[0]
    tg_handle = _LIVE_TG_HANDLES.get(seller.slug, seller.tg_username or seller_short)
    title = f"{contact_name} ({phone})" if phone not in contact_name else contact_name

    note_text = (
        f"📌 [Oisha — Guruhdan lid biriktirildi]\n"
        f"👤 Mijoz: {contact_name} ({phone})\n"
        f"👩‍💼 Masʼul: {seller.name} ({tg_handle}) — {reason}\n"
        f"📝 Izoh: {instruction_text.strip()}"
    )
    lead_id = await _find_or_open_lead(amocrm, phone, title, note_text)
    if not lead_id:
        return (
            f"⚠️ amoCRMʼda <code>{html.escape(phone)}</code> uchun bitim ochib boʻlmadi. "
            f"Tavsiya etilgan masʼul: <b>{html.escape(seller_short)}</b> ({html.escape(tg_handle)})."
        )

    await _patch_generic_lead_title(amocrm, lead_id, title)
    for tag in (seller_short, f"sotuvchi:{seller_short}"):
        if hasattr(amocrm, "add_lead_tag"):
            await amocrm.add_lead_tag(lead_id, tag)

    if hasattr(amocrm, "add_lead_note"):
        note_fn = amocrm.add_lead_note
        if asyncio.iscoroutinefunction(note_fn):
            await note_fn(lead_id, note_text)
        else:
            await asyncio.to_thread(note_fn, lead_id, note_text)

    due_ts, due_label = compute_due_timestamp(instruction_text, now=now)
    task_ok = False
    if hasattr(amocrm, "create_task"):
        task_text = (
            f"🎯 [{seller_short} {tg_handle}] {contact_name} ({phone}) bilan aloqaga chiqish: "
            f"{instruction_text.strip()[:220]}"
        )
        task_ok = bool(await amocrm.create_task(element_id=lead_id, text=task_text, complete_till=due_ts))

    subdomain = getattr(amocrm, "subdomain", "") or "jonbranding"
    link = f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}"
    task_line = f"⏰ <b>Vazifa:</b> {html.escape(due_label)} gacha aloqaga chiqish\n" if task_ok else ""
    return (
        f"📌 <b>Lid biriktirildi</b>\n\n"
        f"👤 <b>Mijoz:</b> {html.escape(contact_name)} (<code>{html.escape(phone)}</code>)\n"
        f"👩‍💼 <b>Masʼul:</b> {html.escape(seller_short)} ({html.escape(tg_handle)}) — {html.escape(reason)}\n"
        f"{task_line}"
        f"🔗 <a href=\"{html.escape(link)}\">amoCRM bitimi #{lead_id}</a>"
    )


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

    async def _observer(handler: Any, event: Any, data: dict) -> Any:
        chat = getattr(event, "chat", None)
        user = getattr(event, "from_user", None)
        if chat is not None and user is not None and not getattr(user, "is_bot", False):
            if int(getattr(chat, "id", 0) or 0) in group_ids_getter():
                extracted = extract_contact_from_message(event)
                if extracted:
                    txt = getattr(event, "text", None) or getattr(event, "caption", None) or ""
                    ctx_cache.remember(int(chat.id), extracted[0], extracted[1], extra_text=txt)
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
        text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
        return is_group_lead_assign_request(text)

    async def _handle(message: Any) -> None:
        text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
        chat_id = int(message.chat.id)
        resolved = extract_contact_from_message(message)
        reply = getattr(message, "reply_to_message", None)
        if resolved is None and reply is not None:
            resolved = extract_contact_from_message(reply)
        cached = ctx_cache.latest(chat_id)
        if resolved is None and cached is not None:
            resolved = (cached.phone, cached.name)
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
        extra = f"{cached.extra_text}\n{text}".strip() if cached and cached.phone == resolved[0] else text
        reply_html = await execute_group_lead_assignment(
            amocrm=amocrm,
            phone=resolved[0],
            contact_name=resolved[1],
            instruction_text=extra,
        )
        await message.reply(reply_html, parse_mode="HTML", disable_web_page_preview=True)

    dispatcher.message.outer_middleware.register(_observer)
    dispatcher.message.register(_handle, _matches)
    logger.info("[GROUP-ASSIGN] Sotuv guruhi lid-biriktirish handleri ulandi.")
    return ctx_cache
