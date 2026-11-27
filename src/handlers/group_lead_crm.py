"""CRM execution va sotuvchi tanlash mantiqi — Sotuv Bolim guruh lid-taqsimlash uchun."""
from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
)
from src.services.core.crm.lead_owner_resolver import _tag_names, owners_from_tags
from src.services.core.crm.team_roster import StaffMember, find_staff
from src.services.core.daily_priority.ownership import (
    SELLER_ALIASES,
    SELLER_FIELD_NAMES,
    configured_seller_field_ids,
)
from src.time_utils import get_local_now

logger = logging.getLogger("OishaGroupLeadAssign")

_NETWORKING_RE = re.compile(
    r"(?i)(?:\btn\s*\d*\b|\bt/n\s*\d*\b|tez\s+natija|networking|trening|tanishuv|klub)"
)
_AFTER_CLASS_RE = re.compile(r"(?i)(?:darsdan\s+keyin|kechqurun|18\s*:\s*30|18\s*:\s*00)")
_SELLER_PREFIX_RE = re.compile(
    r"^(?:sotuvchi|menejer|manager|mas\x27ul|masul|masʻul|masʼul|rep|owner|seller)\s*[:=/]",
    re.IGNORECASE,
)
_LIVE_TG_HANDLES: Dict[str, str] = {
    "shahnoza": "@jonbranding_assistant",
    "rayxona": "@RayxonMenejer",
    "mumtozmaxal": "@MumtozmaxalJonbranding",
}
_KNOWN_SELLER_TOKENS: frozenset[str] = frozenset(
    {"shahnoza", "rayxona", "mumtozmaxal", "baxtiyorjon"}
    | {re.sub(r"[\W_]+", "", a.casefold()) for group in SELLER_ALIASES.values() for a in group}
)


def _norm_token(value: str) -> str:
    return re.sub(r"[\W_]+", "", (value or "").casefold())


def _is_seller_ownership_tag(tag_name: str) -> bool:
    clean = (tag_name or "").strip()
    if not clean:
        return False
    if _SELLER_PREFIX_RE.search(clean):
        return True
    return _norm_token(clean) in _KNOWN_SELLER_TOKENS


def _explicit_seller_from_instruction(instruction_text: str) -> Optional[StaffMember]:
    lowered = (instruction_text or "").lower()
    patterns = (
        ("shahnoza", r"\b(?:shahnoza|shaxnoza|jonbranding_assistant)\w*"),
        ("rayxona", r"\b(?:rayxona|rayxon|rayhona|rayxonmenejer|rayxonjonbranding)\w*"),
        ("mumtozmaxal", r"\b(?:mumtozmaxal|mumtozmahal|mumtoz|mumtozmaxaljonbranding)\w*"),
    )
    hits = [slug for slug, pat in patterns if re.search(pat, lowered)]
    if len(hits) == 1:
        return find_staff(hits[0])
    return None


async def _count_open_closer_loads(amocrm: Any) -> Dict[str, int]:
    loads: Dict[str, int] = {"Rayxona": 0, "Mumtozmaxal": 0}
    if amocrm is None or not hasattr(amocrm, "get_leads"):
        return loads
    try:
        for page in range(1, 9):
            batch = await amocrm.get_leads(
                limit=250,
                page=page,
                **{"filter[pipeline_id][]": SALES_PIPELINE_ID, "order[created_at]": "desc"},
            )
            if not batch:
                break
            for item in batch:
                if item.get("status_id") in (142, 143):
                    continue
                for owner in owners_from_tags(_tag_names(item)):
                    if owner in loads:
                        loads[owner] += 1
            if len(batch) < 250:
                break
    except Exception as exc:
        logger.warning("[GROUP-ASSIGN] Yuklama oʻqilmadi, default tartib ishlatiladi: %s", exc)
    return loads


async def select_seller_for_lead(
    instruction_text: str,
    *,
    contact_context: str = "",
    amocrm: Any = None,
) -> Tuple[StaffMember, str]:
    """Koʻrsatma matni va mijoz kontekstiga koʻra masʼul sotuvchini tanlaydi."""
    explicit = _explicit_seller_from_instruction(instruction_text)
    if explicit is not None:
        return explicit, "rahbar koʻrsatmasi"

    combined = f"{contact_context}\n{instruction_text}".strip()
    if _NETWORKING_RE.search(combined):
        shahnoza = find_staff("shahnoza")
        if shahnoza is not None:
            return shahnoza, "TN / networking qoidasi"

    loads = await _count_open_closer_loads(amocrm)
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


async def _find_active_sales_lead(amocrm: Any, phone: str) -> Optional[Dict[str, Any]]:
    """Faqat SALES_PIPELINE_ID dagi ochiq bitimni qaytaradi (Farmer/boshqa voronkaga tegmaydi)."""
    if hasattr(amocrm, "get_contact_by_phone") and hasattr(amocrm, "get_active_leads_for_contact"):
        c_fn = amocrm.get_contact_by_phone
        contact = await c_fn(phone) if asyncio.iscoroutinefunction(c_fn) else await asyncio.to_thread(c_fn, phone)
        cid = (contact or {}).get("id")
        if not cid:
            return None
        l_fn = amocrm.get_active_leads_for_contact
        leads = await l_fn(int(cid)) if asyncio.iscoroutinefunction(l_fn) else await asyncio.to_thread(l_fn, int(cid))
        sales_leads = [
            ld for ld in (leads or [])
            if ld.get("pipeline_id") in (None, SALES_PIPELINE_ID) and ld.get("status_id") not in (142, 143)
        ]
        if not sales_leads:
            return None
        sales_leads.sort(key=lambda x: int(x.get("updated_at") or x.get("created_at") or 0), reverse=True)
        return sales_leads[0]

    if hasattr(amocrm, "find_active_lead_by_phone"):
        fn = amocrm.find_active_lead_by_phone
        lead = await fn(phone) if asyncio.iscoroutinefunction(fn) else await asyncio.to_thread(fn, phone)
        if lead and lead.get("pipeline_id") in (None, SALES_PIPELINE_ID):
            return lead
    return None


async def _find_or_open_sales_lead(amocrm: Any, phone: str, title: str) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    existing = await _find_active_sales_lead(amocrm, phone)
    if existing and existing.get("id"):
        return int(existing["id"]), existing
    if hasattr(amocrm, "create_lead"):
        created = await amocrm.create_lead(
            name=title,
            phone=phone,
            pipeline_id=SALES_PIPELINE_ID,
            status_id=SALES_NEW_STATUS_ID,
        )
        return (int(created), None) if created else (None, None)
    if hasattr(amocrm, "ensure_lead"):
        created = await amocrm.ensure_lead(
            name=title,
            phone=phone,
            pipeline_id=SALES_PIPELINE_ID,
            status_id=SALES_NEW_STATUS_ID,
        )
        return (int(created), None) if created else (None, None)
    return None, None


def _build_ownership_patch(lead: Dict[str, Any], seller_short: str, desired_title: str) -> Dict[str, Any]:
    raw_tags = (lead.get("_embedded") or {}).get("tags") or lead.get("tags") or []
    kept = [
        {"name": str(t.get("name") if isinstance(t, dict) else t).strip()}
        for t in raw_tags
        if str(t.get("name") if isinstance(t, dict) else t).strip()
        and not _is_seller_ownership_tag(str(t.get("name") if isinstance(t, dict) else t))
    ]
    kept.extend([{"name": seller_short}, {"name": f"sotuvchi:{seller_short}"}])
    payload: Dict[str, Any] = {"_embedded": {"tags": kept}}

    cur_name = str(lead.get("name") or "").strip()
    if not cur_name or cur_name.startswith(("Сделка #", "DM Lead:")):
        payload["name"] = desired_title

    trusted_ids = configured_seller_field_ids()
    cf_updates: List[Dict[str, Any]] = []
    for field in lead.get("custom_fields_values") or []:
        if not isinstance(field, dict) or not field.get("field_id"):
            continue
        fid = int(field["field_id"])
        fname_norm = _norm_token(str(field.get("field_name") or ""))
        if fname_norm in SELLER_FIELD_NAMES or fid in trusted_ids:
            cf_updates.append({"field_id": fid, "values": [{"value": seller_short}]})
    if cf_updates:
        payload["custom_fields_values"] = cf_updates
    return payload


async def _apply_exclusive_seller_ownership(
    amocrm: Any,
    lead_id: int,
    seller_short: str,
    desired_title: str,
    initial_lead: Optional[Dict[str, Any]] = None,
) -> bool:
    lead = initial_lead or (await amocrm.get_lead(lead_id) if hasattr(amocrm, "get_lead") else None) or {}
    if hasattr(amocrm, "_get_headers") and hasattr(amocrm, "base_url"):
        import requests

        payload = _build_ownership_patch(lead, seller_short, desired_title)
        url = f"{amocrm.base_url}/api/v4/leads/{lead_id}"
        resp = await asyncio.to_thread(
            requests.patch, url, headers=amocrm._get_headers(), json=payload, timeout=20
        )
        return resp.status_code in (200, 204)

    ok = True
    for tag in (seller_short, f"sotuvchi:{seller_short}"):
        if hasattr(amocrm, "add_lead_tag"):
            ok = bool(await amocrm.add_lead_tag(lead_id, tag)) and ok
    return ok


async def execute_group_lead_assignment(
    *,
    amocrm: Any,
    phone: str,
    contact_name: str,
    instruction_text: str,
    contact_context: str = "",
    now: Optional[datetime] = None,
) -> str:
    merged_context = f"{contact_name}\n{contact_context}".strip()
    seller, reason = await select_seller_for_lead(
        instruction_text, contact_context=merged_context, amocrm=amocrm
    )
    seller_short = seller.name.split()[0]
    tg_handle = _LIVE_TG_HANDLES.get(seller.slug, seller.tg_username or seller_short)
    title = f"{contact_name} ({phone})" if phone not in contact_name else contact_name

    lead_id, existing_lead = await _find_or_open_sales_lead(amocrm, phone, title)
    if not lead_id:
        return (
            f"⚠️ amoCRMʼda <code>{html.escape(phone)}</code> uchun bitim ochib boʻlmadi. "
            f"Tavsiya etilgan masʼul: <b>{html.escape(seller_short)}</b> ({html.escape(tg_handle)})."
        )

    owner_ok = await _apply_exclusive_seller_ownership(
        amocrm, lead_id, seller_short, title, initial_lead=existing_lead
    )
    if not owner_ok:
        return f"⚠️ amoCRM bitimi #{lead_id} da masʼul tegini yangilab boʻlmadi."

    note_text = (
        f"📌 [Oisha — Guruhdan lid biriktirildi]\n"
        f"👤 Mijoz: {contact_name} ({phone})\n"
        f"👩‍💼 Masʼul: {seller.name} ({tg_handle}) — {reason}\n"
        f"📝 Izoh: {instruction_text.strip()}"
    )
    if hasattr(amocrm, "add_lead_note"):
        note_fn = amocrm.add_lead_note
        await (note_fn(lead_id, note_text) if asyncio.iscoroutinefunction(note_fn) else asyncio.to_thread(note_fn, lead_id, note_text))

    due_ts, due_label = compute_due_timestamp(instruction_text, now=now)
    task_ok = False
    if hasattr(amocrm, "create_task"):
        task_text = f"🎯 [{seller_short} {tg_handle}] {contact_name} ({phone}) bilan aloqaga chiqish: {instruction_text.strip()[:220]}"
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
