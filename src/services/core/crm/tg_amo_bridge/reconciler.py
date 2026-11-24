"""Background reconciliation scanner and periodic loop for split TG/phone deals."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .analyzer import (
    CLOSED_STATUS_IDS,
    LeadProfile,
    contact_phones,
    extract_phone_from_text,
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
                    {
                        "source": outcome.merged_source_lead_id,
                        "target": outcome.target_lead_id,
                        "phone": outcome.phone,
                    }
                )
            elif outcome.status == "conflict":
                report.conflicts += 1
        except Exception as exc:
            report.errors += 1
            logger.warning("[TG-MERGE] link scan error for %s: %s", link.get("tg_user_id"), type(exc).__name__)


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
) -> tuple[Dict[str, List[LeadProfile]], Dict[int, Optional[str]]]:
    leads = await crm.get_leads(limit=limit, with_contacts=True)
    active_rows: List[tuple[Dict[str, Any], int]] = []
    open_counts_by_contact: Dict[int, int] = {}
    for lead in leads:
        lid = int(lead.get("id") or 0)
        sid = int(lead.get("status_id") or 0)
        if lid <= 0 or sid in CLOSED_STATUS_IDS:
            continue
        report.checked_leads += 1
        c_refs = (lead.get("_embedded") or {}).get("contacts") or []
        cid = int(c_refs[0].get("id") or 0) if c_refs else 0
        if cid <= 0:
            continue
        active_rows.append((lead, cid))
        open_counts_by_contact[cid] = open_counts_by_contact.get(cid, 0) + 1

    groups: Dict[str, List[LeadProfile]] = {}
    contact_cache: Dict[int, Dict[str, Any]] = {}
    call_cache: Dict[int, int] = {}
    chat_id_cache: Dict[int, Optional[str]] = {}

    for lead, cid in active_rows:
        if cid not in contact_cache:
            contact_cache[cid] = await crm.get_contact_details_async(cid) or {}
            call_cache[cid] = (
                await crm.get_contact_call_notes_count(cid)
                if hasattr(crm, "get_contact_call_notes_count")
                else 0
            )
            chats = await crm.get_contact_chats(contact_id=cid) if hasattr(crm, "get_contact_chats") else []
            chat_id_cache[cid] = str(chats[0].get("chat_id") or "") if chats else None

        phones = await _extract_lead_phones(crm, lead, contact_cache[cid])
        if not phones or is_internal_team_phone(phones[0]):
            continue

        single_deal_chat = bool(chat_id_cache[cid] and open_counts_by_contact.get(cid, 0) == 1)
        groups.setdefault(phones[0][-9:], []).append(
            LeadProfile(
                lead_id=int(lead["id"]), contact_id=cid, name=str(lead.get("name") or ""),
                status_id=int(lead.get("status_id") or 0), pipeline_id=int(lead.get("pipeline_id") or 0),
                price=int(lead.get("price") or 0), created_at=int(lead.get("created_at") or 0),
                updated_at=int(lead.get("updated_at") or 0), call_count=call_cache[cid],
                has_chat=bool(chat_id_cache[cid]), tg_provenance=single_deal_chat,
                notes_count=0, tags=lead_tags(lead), phones=phones,
            )
        )
    return groups, chat_id_cache


async def scan_and_merge_existing(
    merger: TelegramDealAutoMerger, *, limit: int = 100
) -> ScanReport:
    """Scan cached TG links and active CRM leads to auto-merge split TG/phone deals."""
    report = ScanReport(dry_run=merger.dry_run)
    if not merger.crm:
        return report

    await _scan_cached_links(merger, report, limit)
    groups, chat_id_cache = await _group_active_leads_by_phone(merger.crm, report, limit)

    for tail, group in groups.items():
        if len(group) < 2:
            continue
        decision = pick_best_pair(group)
        if not decision:
            report.skipped += 1
            continue
        phone_full = next((p.phones[0] for p in group if p.phones), f"998{tail}")
        amo_chat_id = chat_id_cache.get(decision.source_contact_id) or None
        try:
            status = await merger.execute_decision(
                decision, phone=phone_full, amo_chat_id=amo_chat_id
            )
            if status == "merged":
                report.merged += 1
                report.details.append(
                    {
                        "source": decision.source_lead_id,
                        "target": decision.target_lead_id,
                        "phone": phone_full,
                    }
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
    merger: TelegramDealAutoMerger, *, interval_seconds: int = 300, limit: int = 100
) -> None:
    """Periodic background reconciliation for already-split Telegram/phone deals."""
    delay = max(30, int(interval_seconds))
    logger.info("[TG-MERGE] Background reconciler started (interval=%ss)", delay)
    while True:
        try:
            report = await scan_and_merge_existing(merger, limit=limit)
            if report.merged or report.conflicts:
                logger.info(
                    "[TG-MERGE] Scan complete: merged=%d linked_only=%d conflicts=%d errors=%d",
                    report.merged,
                    report.linked_only,
                    report.conflicts,
                    report.errors,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[TG-MERGE] Background scan failed: %s", type(exc).__name__)
        await asyncio.sleep(delay)
