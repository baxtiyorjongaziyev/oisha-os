"""Idempotent, race-safe execution of Telegram <-> Phone PairDecision mutations."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from .analyzer import PairDecision, format_merge_note
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.executor")

MERGED_TARGET_TAG = "TG_MERGED"
MERGED_SOURCE_TAG = "AUTO_MERGED_TG"
REVIEW_CONFLICT_TAG = "TG_MERGE_REVIEW"

_LEAD_LOCKS: Dict[int, asyncio.Lock] = {}


def note_text(note: Dict[str, Any]) -> str:
    params = note.get("params") or {}
    return str(params.get("text") or note.get("text") or "").strip()


async def _migrate_open_tasks(
    crm: Any, source_lead_id: int, target_lead_id: int
) -> Tuple[int, int]:
    """Reassign open tasks from source to target without creating duplicates."""
    if not hasattr(crm, "get_lead_open_tasks"):
        return 0, 0
    tasks = await crm.get_lead_open_tasks(source_lead_id)
    if not tasks:
        return 0, 0
    migrated = 0
    failed = 0
    for task in tasks:
        tid = int(task.get("id") or 0)
        if tid > 0 and hasattr(crm, "reassign_task_to_lead"):
            if await crm.reassign_task_to_lead(tid, target_lead_id):
                migrated += 1
            else:
                failed += 1
        else:
            failed += 1
    return migrated, failed


async def _record_audit(
    store: MessageStore,
    decision: PairDecision,
    *,
    phone: str,
    tg_user_id: Optional[int],
    status: str,
    reason: Optional[str] = None,
) -> None:
    await store.record_merge(
        source_lead_id=decision.source_lead_id,
        target_lead_id=decision.target_lead_id,
        source_contact_id=decision.source_contact_id,
        target_contact_id=decision.target_contact_id,
        tg_user_id=tg_user_id,
        phone=phone,
        status=status,
        reason=reason if reason is not None else decision.reason,
    )


async def _target_already_noted(crm: Any, target_lead_id: int, marker: str) -> bool:
    if not hasattr(crm, "get_lead_notes"):
        return False
    for note in await crm.get_lead_notes(target_lead_id):
        if marker in note_text(note):
            return True
    return False


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
    if dry_run:
        await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status="dry_run")
        return "linked_only"
    link_ok = True
    if decision.target_contact_id != decision.source_contact_id:
        link_ok = bool(await crm.link_contact_to_lead_async(decision.source_lead_id, decision.target_contact_id))
    note_ok = bool(
        await crm.add_lead_note_async(
            decision.source_lead_id,
            f"🔗 [TG-AMO TARIX] Bu mijozning avvalgi yopilgan sdelkasi #{decision.target_lead_id} "
            f"(raqam: +{phone}) topildi. Yangi faol Telegram sdelkasi saqlandi.",
        )
    )
    final_status = "linked_only" if (link_ok and note_ok) else "incomplete"
    await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status=final_status)
    return final_status


async def _ensure_links(crm: Any, decision: PairDecision, amo_chat_id: Optional[str]) -> Tuple[bool, bool]:
    contact_ok = True
    if decision.source_contact_id != decision.target_contact_id:
        contact_ok = bool(await crm.link_contact_to_lead_async(decision.target_lead_id, decision.source_contact_id))
    chat_ok = True
    if amo_chat_id and hasattr(crm, "link_chat_to_contact"):
        chat_ok = bool(await crm.link_chat_to_contact(decision.target_contact_id, amo_chat_id))
        if (
            not chat_ok
            and getattr(crm, "_chat_channel_unlinked", False)
            and decision.source_contact_id != decision.target_contact_id
            and contact_ok
        ):
            chat_ok = True
    return chat_ok, contact_ok


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
    chat_ok, contact_ok = await _ensure_links(crm, decision, amo_chat_id)

    raw_notes = await crm.get_lead_notes(decision.source_lead_id) if hasattr(crm, "get_lead_notes") else []
    source_notes = [note_text(n) for n in raw_notes if note_text(n)]
    migrated_tasks, failed_tasks = await _migrate_open_tasks(
        crm, decision.source_lead_id, decision.target_lead_id
    )

    marker = f"#{decision.source_lead_id} -> #{decision.target_lead_id}"
    if await _target_already_noted(crm, decision.target_lead_id, marker):
        note_ok = True
    else:
        target_note = format_merge_note(
            decision=decision, phone=phone, tg_user_id=tg_user_id,
            username=username, source_notes=source_notes, migrated_tasks=migrated_tasks,
        )
        note_ok = bool(await crm.add_lead_note_async(decision.target_lead_id, target_note))

    # Never close the source deal unless every required link, task move, and note succeeded.
    if not (chat_ok and contact_ok and failed_tasks == 0 and note_ok):
        fail_reason = f"transfer_failed(chat={chat_ok},contact={contact_ok},failed_tasks={failed_tasks},note={note_ok})"
        await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status="incomplete", reason=fail_reason)
        logger.warning("[TG-MERGE] Incomplete #%s -> #%s: %s", decision.source_lead_id, decision.target_lead_id, fail_reason)
        return "incomplete"

    await crm.add_lead_tag(decision.target_lead_id, MERGED_TARGET_TAG)
    await crm.add_lead_note_async(
        decision.source_lead_id,
        f"🔗 [AUTO-MERGE] Ushbu Telegram sdelkasi #{decision.target_lead_id} asosiy telefon "
        f"sdelkasiga avtomatik birlashtirildi va yopildi (raqam: +{phone}).",
    )
    await crm.add_lead_tag(decision.source_lead_id, MERGED_SOURCE_TAG)
    closed = bool(await crm.close_duplicate_lead(decision.source_lead_id, loss_reason_id=loss_reason_id))
    final_status = "merged" if closed else "incomplete"
    await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status=final_status)
    logger.info("[TG-MERGE] %s: #%s -> #%s (phone=+%s, tasks=%s)", final_status, decision.source_lead_id, decision.target_lead_id, phone, migrated_tasks)
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
    """Atomically claim source_lead_id and apply PairDecision with zero data loss."""
    if decision.action not in {"merge", "link_only", "conflict"}:
        return "skipped"

    lock = _LEAD_LOCKS.setdefault(int(decision.source_lead_id), asyncio.Lock())
    async with lock:
        if dry_run:
            prev = await store.get_merge_record(decision.source_lead_id)
            if prev and prev.get("status") in {"merged", "linked_only", "conflict"}:
                return prev["status"]
            if decision.action == "conflict":
                return await _handle_conflict(crm, store, decision, phone=phone, tg_user_id=tg_user_id, dry_run=True)
            if decision.action == "link_only":
                return await _handle_link_only(crm, store, decision, phone=phone, tg_user_id=tg_user_id, dry_run=True)
            await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status="dry_run")
            return "merged"

        claimed, existing_status = await store.try_claim_merge(
            source_lead_id=decision.source_lead_id,
            target_lead_id=decision.target_lead_id,
            source_contact_id=decision.source_contact_id,
            target_contact_id=decision.target_contact_id,
            tg_user_id=tg_user_id,
            phone=phone,
            reason=decision.reason,
        )
        if not claimed:
            return existing_status or "skipped"

        try:
            if decision.action == "conflict":
                return await _handle_conflict(crm, store, decision, phone=phone, tg_user_id=tg_user_id, dry_run=False)
            if decision.action == "link_only":
                return await _handle_link_only(crm, store, decision, phone=phone, tg_user_id=tg_user_id, dry_run=False)
            return await _apply_merge(
                crm, store, decision, phone=phone, amo_chat_id=amo_chat_id,
                tg_user_id=tg_user_id, username=username, loss_reason_id=loss_reason_id,
            )
        except Exception:
            await _record_audit(store, decision, phone=phone, tg_user_id=tg_user_id, status="incomplete", reason="exception")
            raise
