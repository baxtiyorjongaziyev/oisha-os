"""Idempotent execution of Telegram <-> Phone PairDecision mutations in amoCRM."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .analyzer import PairDecision, format_merge_note
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.executor")

MERGED_TARGET_TAG = "TG_MERGED"
MERGED_SOURCE_TAG = "AUTO_MERGED_TG"
REVIEW_CONFLICT_TAG = "TG_MERGE_REVIEW"


def note_text(note: Dict[str, Any]) -> str:
    params = note.get("params") or {}
    return str(params.get("text") or note.get("text") or "").strip()


async def _migrate_open_tasks(crm: Any, source_lead_id: int, target_lead_id: int) -> int:
    if not (hasattr(crm, "get_lead_open_tasks") and hasattr(crm, "create_task")):
        return 0
    migrated = 0
    for task in await crm.get_lead_open_tasks(source_lead_id):
        t_text = str(task.get("text") or "").strip()
        complete_till = int(task.get("complete_till") or 0)
        if not (t_text and complete_till > 0):
            continue
        created = await crm.create_task(
            element_id=target_lead_id,
            text=f"[Telegram #{source_lead_id} dan koʻchirildi] {t_text}",
            complete_till=complete_till,
            responsible_user_id=task.get("responsible_user_id"),
        )
        if created:
            migrated += 1
    return migrated


async def _record_audit(
    store: MessageStore,
    decision: PairDecision,
    *,
    phone: str,
    tg_user_id: Optional[int],
    status: str,
) -> None:
    await store.record_merge(
        source_lead_id=decision.source_lead_id,
        target_lead_id=decision.target_lead_id,
        source_contact_id=decision.source_contact_id,
        target_contact_id=decision.target_contact_id,
        tg_user_id=tg_user_id,
        phone=phone,
        status=status,
        reason=decision.reason,
    )


async def _handle_conflict(
    crm: Any,
    store: MessageStore,
    decision: PairDecision,
    *,
    phone: str,
    tg_user_id: Optional[int],
    dry_run: bool,
) -> str:
    if not dry_run:
        await crm.add_lead_tag(decision.source_lead_id, REVIEW_CONFLICT_TAG)
        await crm.add_lead_note_async(
            decision.source_lead_id,
            f"⚠️ [TG-AMO MERGE REVIEW] #{decision.target_lead_id} bilan bir xil raqam (+{phone}), "
            f"lekin avtomatik yopilmadi ({decision.reason}). Qoʻlda tekshiring.",
        )
    await _record_audit(
        store, decision, phone=phone, tg_user_id=tg_user_id, status="dry_run" if dry_run else "conflict"
    )
    return "conflict"


async def _handle_link_only(
    crm: Any,
    store: MessageStore,
    decision: PairDecision,
    *,
    phone: str,
    tg_user_id: Optional[int],
    dry_run: bool,
) -> str:
    if not dry_run:
        if decision.target_contact_id != decision.source_contact_id:
            await crm.link_contact_to_lead_async(decision.source_lead_id, decision.target_contact_id)
        await crm.add_lead_note_async(
            decision.source_lead_id,
            f"🔗 [TG-AMO TARIX] Bu mijozning avvalgi yopilgan sdelkasi #{decision.target_lead_id} "
            f"(raqam: +{phone}) topildi. Yangi faol Telegram sdelkasi saqlandi.",
        )
    await _record_audit(
        store, decision, phone=phone, tg_user_id=tg_user_id, status="dry_run" if dry_run else "linked_only"
    )
    return "linked_only"


async def _apply_merge(
    crm: Any,
    store: MessageStore,
    decision: PairDecision,
    *,
    phone: str,
    amo_chat_id: Optional[str],
    tg_user_id: Optional[int],
    username: Optional[str],
    loss_reason_id: Optional[int],
) -> str:
    if amo_chat_id and hasattr(crm, "link_chat_to_contact"):
        await crm.link_chat_to_contact(decision.target_contact_id, amo_chat_id)
    if decision.source_contact_id != decision.target_contact_id:
        await crm.link_contact_to_lead_async(decision.target_lead_id, decision.source_contact_id)

    raw_notes = await crm.get_lead_notes(decision.source_lead_id) if hasattr(crm, "get_lead_notes") else []
    source_notes = [note_text(n) for n in raw_notes if note_text(n)]
    migrated_tasks = await _migrate_open_tasks(crm, decision.source_lead_id, decision.target_lead_id)

    target_note = format_merge_note(
        decision=decision,
        phone=phone,
        tg_user_id=tg_user_id,
        username=username,
        source_notes=source_notes,
        migrated_tasks=migrated_tasks,
    )
    await crm.add_lead_note_async(decision.target_lead_id, target_note)
    await crm.add_lead_tag(decision.target_lead_id, MERGED_TARGET_TAG)
    await crm.add_lead_note_async(
        decision.source_lead_id,
        f"🔗 [AUTO-MERGE] Ushbu Telegram sdelkasi #{decision.target_lead_id} asosiy telefon "
        f"sdelkasiga avtomatik birlashtirildi va yopildi (raqam: +{phone}).",
    )
    await crm.add_lead_tag(decision.source_lead_id, MERGED_SOURCE_TAG)
    closed = await crm.close_duplicate_lead(decision.source_lead_id, loss_reason_id=loss_reason_id)
    final_status = "merged" if closed else "linked_only"
    await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status=final_status)
    logger.info(
        "[TG-MERGE] %s: #%s -> #%s (phone=+%s, tasks=%s)",
        final_status,
        decision.source_lead_id,
        decision.target_lead_id,
        phone,
        migrated_tasks,
    )
    return final_status


async def execute_pair_decision(
    crm: Any,
    store: MessageStore,
    decision: PairDecision,
    *,
    phone: str,
    amo_chat_id: Optional[str] = None,
    tg_user_id: Optional[int] = None,
    username: Optional[str] = None,
    dry_run: bool = False,
    loss_reason_id: Optional[int] = None,
) -> str:
    """Apply a PairDecision idempotently with zero data loss."""
    prev = await store.get_merge_record(decision.source_lead_id)
    if prev and prev.get("status") in {"merged", "linked_only", "conflict"}:
        return prev["status"]

    if decision.action == "conflict":
        return await _handle_conflict(crm, store, decision, phone=phone, tg_user_id=tg_user_id, dry_run=dry_run)
    if decision.action == "link_only":
        return await _handle_link_only(crm, store, decision, phone=phone, tg_user_id=tg_user_id, dry_run=dry_run)
    if decision.action != "merge":
        return "skipped"
    if dry_run:
        await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status="dry_run")
        return "merged"
    return await _apply_merge(
        crm,
        store,
        decision,
        phone=phone,
        amo_chat_id=amo_chat_id,
        tg_user_id=tg_user_id,
        username=username,
        loss_reason_id=loss_reason_id,
    )
