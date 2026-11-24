"""Background reconciliation scanner and periodic loop for split TG/phone deals."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .analyzer import (
    CLOSED_STATUS_IDS,
    LeadProfile,
    contact_phones,
    count_call_notes,
    extract_phone_from_text,
    has_call_lead_marker,
    is_internal_team_phone,
    lead_tags,
    pick_best_pair,
)
from .automerge import TelegramDealAutoMerger, _note_text

logger = logging.getLogger("TgAmoBridge.reconciler")


@dataclass
class ScanReport:
    checked_links: int = 0
    checked_leads: int = 0
    merged: int = 0
    linked_only: int = 0
    conflicts: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run: bool = False
    details: List[Dict[str, Any]] = field(default_factory=list)


async def _scan_cached_links(merger: TelegramDealAutoMerger, report: ScanReport, limit: int) -> None:
    links = await merger.store.list_chat_links_with_phone(limit=limit)
    for link in links:
        report.checked_links += 1
        try:
            outcome = await merger.ensure_chat_linked_before_send(
                peer_id=int(link["tg_user_id"]),
                client_name=link.get("username") or str(link["tg_user_id"]),
                sender_phone=link.get("phone"),
                username=link.get("username"),
                force_recheck=True,
            )
            if outcome.status == "merged":
                report.merged += 1
                report.details.append(
                    {"source": outcome.merged_source_lead_id, "target": outcome.target_lead_id, "phone": outcome.phone}
                )
            elif outcome.status == "conflict":
                report.conflicts += 1
        except Exception as exc:
            report.errors += 1
            logger.warning("[TG-MERGE] link scan error for %s: %s", link.get("tg_user_id"), type(exc).__name__)


async def _fetch_recent_active_leads(crm: Any, limit: int) -> List[Dict[str, Any]]:
    """Fetch recent active leads ordered by updated_at desc across up to 3 pages."""
    active: List[Dict[str, Any]] = []
    seen: set[int] = set()
    per_page = min(max(int(limit), 1), 250)
    max_pages = 3 if limit >= 150 else 2
    for page in range(1, max_pages + 1):
        try:
            batch = await crm.get_leads(
                limit=per_page,
                page=page,
                with_contacts=True,
                **{"order[updated_at]": "desc"},
            )
        except TypeError:
            batch = await crm.get_leads(limit=per_page, with_contacts=True)
            max_pages = 1
        if not batch:
            break
        for lead in batch:
            lid = int(lead.get("id") or 0)
            sid = int(lead.get("status_id") or 0)
            if lid <= 0 or lid in seen or sid in CLOSED_STATUS_IDS:
                continue
            seen.add(lid)
            active.append(lead)
            if len(active) >= limit:
                return active
        if len(batch) < per_page or page >= max_pages:
            break
    return active


async def _fetch_talks_maps(crm: Any) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Return (lead_id -> chat_id, contact_id -> chat_id) from GET /api/v4/talks."""
    if not hasattr(crm, "get_talks_async"):
        return {}, {}
    lead_talks: Dict[int, str] = {}
    contact_talks: Dict[int, str] = {}
    for talk in await crm.get_talks_async(limit=250):
        chat_id = str(talk.get("chat_id") or "").strip()
        if not chat_id:
            continue
        cid = int(talk.get("contact_id") or 0)
        if cid > 0 and cid not in contact_talks:
            contact_talks[cid] = chat_id
        if str(talk.get("entity_type") or "").lower() == "lead":
            lid = int(talk.get("entity_id") or 0)
            if lid > 0 and lid not in lead_talks:
                lead_talks[lid] = chat_id
    return lead_talks, contact_talks


async def _extract_lead_phones(
    crm: Any, lead: Dict[str, Any], contact: Dict[str, Any]
) -> tuple[str, ...]:
    phones = contact_phones(contact)
    if phones:
        return phones
    text_phone = extract_phone_from_text(str(lead.get("name") or ""))
    if not text_phone and hasattr(crm, "get_lead_notes"):
        for note in (await crm.get_lead_notes(int(lead["id"])))[:10]:
            text_phone = extract_phone_from_text(_note_text(note))
            if text_phone:
                break
    return (text_phone,) if text_phone and not is_internal_team_phone(text_phone) else ()


async def _group_active_leads_by_phone(
    crm: Any, report: ScanReport, limit: int
) -> Tuple[Dict[str, List[Tuple[Dict[str, Any], int, tuple[str, ...]]]], Dict[int, int], Dict[int, str], Dict[int, str]]:
    leads = await _fetch_recent_active_leads(crm, limit)
    lead_talks, contact_talks = await _fetch_talks_maps(crm)
    active_rows: List[Tuple[Dict[str, Any], int]] = []
    open_counts: Dict[int, int] = {}
    for lead in leads:
        report.checked_leads += 1
        c_refs = (lead.get("_embedded") or {}).get("contacts") or []
        cid = int(c_refs[0].get("id") or 0) if c_refs else 0
        if cid <= 0:
            continue
        active_rows.append((lead, cid))
        open_counts[cid] = open_counts.get(cid, 0) + 1

    raw_groups: Dict[str, List[Tuple[Dict[str, Any], int, tuple[str, ...]]]] = {}
    contact_cache: Dict[int, Dict[str, Any]] = {}
    for lead, cid in active_rows:
        if cid not in contact_cache:
            contact_cache[cid] = await crm.get_contact_details_async(cid) or {}
        phones = await _extract_lead_phones(crm, lead, contact_cache[cid])
        if not phones or is_internal_team_phone(phones[0]):
            continue
        raw_groups.setdefault(phones[0][-9:], []).append((lead, cid, phones))
    return raw_groups, open_counts, lead_talks, contact_talks


async def _hydrate_group_profiles(
    crm: Any,
    rows: List[Tuple[Dict[str, Any], int, tuple[str, ...]]],
    open_counts: Dict[int, int],
    lead_talks: Dict[int, str],
    contact_talks: Dict[int, str],
) -> Tuple[List[LeadProfile], Dict[int, Optional[str]]]:
    profiles: List[LeadProfile] = []
    chat_by_contact: Dict[int, Optional[str]] = {}
    for lead, cid, phones in rows:
        lid = int(lead["id"])
        name = str(lead.get("name") or "")
        tags = lead_tags(lead)
        notes = await crm.get_lead_notes(lid) if hasattr(crm, "get_lead_notes") else []
        contact_calls = (
            await crm.get_contact_call_notes_count(cid)
            if hasattr(crm, "get_contact_call_notes_count") else 0
        )
        lead_calls = count_call_notes(notes)
        total_calls = contact_calls + lead_calls
        if total_calls == 0 and has_call_lead_marker(name, tags):
            total_calls = 1

        chat_id = lead_talks.get(lid) or contact_talks.get(cid)
        if not chat_id and hasattr(crm, "get_contact_chats"):
            chats = await crm.get_contact_chats(contact_id=cid)
            for item in chats:
                if str(item.get("entity_type") or "").lower() == "lead" and int(item.get("entity_id") or 0) == lid:
                    lead_talks[lid] = str(item.get("chat_id") or "")
                if not chat_id and item.get("chat_id"):
                    chat_id = str(item["chat_id"])
        chat_by_contact[cid] = chat_id
        has_deal_talk = lid in lead_talks
        tg_prov = (has_deal_talk and total_calls == 0) or (
            bool(chat_id) and open_counts.get(cid, 0) == 1 and total_calls == 0
        )
        profiles.append(
            LeadProfile(
                lead_id=lid, contact_id=cid, name=name,
                status_id=int(lead.get("status_id") or 0), pipeline_id=int(lead.get("pipeline_id") or 0),
                price=int(lead.get("price") or 0), created_at=int(lead.get("created_at") or 0),
                updated_at=int(lead.get("updated_at") or 0), call_count=total_calls,
                has_chat=bool(chat_id), tg_provenance=tg_prov,
                notes_count=len(notes), tags=tags, phones=phones,
            )
        )
    return profiles, chat_by_contact


async def scan_and_merge_existing(
    merger: TelegramDealAutoMerger, *, limit: int = 250
) -> ScanReport:
    """Scan cached TG links and recent active CRM leads to auto-merge split TG/phone deals."""
    report = ScanReport(dry_run=merger.dry_run)
    if not merger.crm:
        return report

    await _scan_cached_links(merger, report, limit)
    raw_groups, open_counts, lead_talks, contact_talks = await _group_active_leads_by_phone(
        merger.crm, report, limit
    )
    for tail, rows in raw_groups.items():
        if len(rows) < 2:
            continue
        group, chat_by_contact = await _hydrate_group_profiles(
            merger.crm, rows, open_counts, lead_talks, contact_talks
        )
        decision = pick_best_pair(group)
        if not decision:
            report.skipped += 1
            continue
        phone_full = next((p.phones[0] for p in group if p.phones), f"998{tail}")
        amo_chat_id = lead_talks.get(decision.source_lead_id) or chat_by_contact.get(decision.source_contact_id)
        try:
            status = await merger.execute_decision(
                decision, phone=phone_full, amo_chat_id=amo_chat_id
            )
            if status == "merged":
                report.merged += 1
                report.details.append(
                    {"source": decision.source_lead_id, "target": decision.target_lead_id, "phone": phone_full}
                )
            elif status == "linked_only":
                report.linked_only += 1
            elif status == "conflict":
                report.conflicts += 1
            else:
                report.skipped += 1
        except Exception as exc:
            report.errors += 1
            logger.warning("[TG-MERGE] group scan error (%s): %s", tail, type(exc).__name__)
    return report


async def automerge_loop(
    merger: TelegramDealAutoMerger, *, interval_seconds: int = 300, limit: int = 250
) -> None:
    """Periodic background reconciliation for already-split Telegram/phone deals."""
    delay = max(30, int(interval_seconds))
    logger.info("[TG-MERGE] Background reconciler started (interval=%ss, limit=%d)", delay, limit)
    while True:
        try:
            report = await scan_and_merge_existing(merger, limit=limit)
            logger.info(
                "[TG-MERGE] Scan complete: leads=%d merged=%d linked_only=%d conflicts=%d errors=%d",
                report.checked_leads, report.merged, report.linked_only, report.conflicts, report.errors,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[TG-MERGE] Background scan failed: %s", type(exc).__name__)
        await asyncio.sleep(delay)
