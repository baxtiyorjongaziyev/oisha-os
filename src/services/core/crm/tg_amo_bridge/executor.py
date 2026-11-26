"""Idempotent, race-safe execution of Telegram <-> Phone PairDecision mutations."""
from __future__ import annotations

import asyncio
import contextlib
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


def _has_value(field: Dict[str, Any]) -> bool:
    for v in field.get("values") or []:
        val = v.get("value") if isinstance(v, dict) else v
        if val not in (None, "", [], {}):
            return True
        if isinstance(v, dict) and v.get("enum_id"):
            return True
    return False


def build_field_transfer(source: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    """Fill-only payload: copy source price/custom fields that target lacks. Never overwrites."""
    payload: Dict[str, Any] = {}
    if int(target.get("price") or 0) <= 0 and int(source.get("price") or 0) > 0:
        payload["price"] = int(source["price"])
    filled = {
        int(f.get("field_id") or 0)
        for f in (target.get("custom_fields_values") or [])
        if _has_value(f)
    }
    cf_values = []
    for f in source.get("custom_fields_values") or []:
        fid = int(f.get("field_id") or 0)
        if fid <= 0 or fid in filled or not _has_value(f):
            continue
        values = []
        for v in f.get("values") or []:
            if not isinstance(v, dict):
                continue
            item = {k: v[k] for k in ("value", "enum_id", "enum_code") if v.get(k) not in (None, "")}
            if item:
                values.append(item)
        if values:
            cf_values.append({"field_id": fid, "values": values})
    if cf_values:
        payload["custom_fields_values"] = cf_values
    return payload


async def _transfer_lead_fields(crm: Any, source_lead_id: int, target_lead_id: int) -> Tuple[bool, int]:
    """Copy missing price/custom fields from source to target. Returns (ok, fields_copied)."""
    if not (hasattr(crm, "get_lead") and hasattr(crm, "patch_lead")):
        return True, 0
    source = await crm.get_lead(source_lead_id)
    target = await crm.get_lead(target_lead_id)
    if not source or not target:
        return False, 0
    payload = build_field_transfer(source, target)
    if not payload:
        return True, 0
    ok = bool(await crm.patch_lead(target_lead_id, payload))
    copied = len(payload.get("custom_fields_values") or []) + (1 if "price" in payload else 0)
    return ok, copied if ok else 0


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
        if contact_ok and hasattr(crm, "verify_contact_linked_to_lead"):
            contact_ok = bool(await crm.verify_contact_linked_to_lead(decision.target_lead_id, decision.source_contact_id))
    chat_ok = True
    if amo_chat_id and hasattr(crm, "link_chat_to_contact"):
        chat_ok = bool(await crm.link_chat_to_contact(decision.target_contact_id, amo_chat_id))
        unlinked = (
            crm.is_chat_channel_unlinked()
            if hasattr(crm, "is_chat_channel_unlinked")
            else bool(getattr(crm, "_chat_channel_unlinked", False))
        )
        if not chat_ok and unlinked and decision.source_contact_id != decision.target_contact_id and contact_ok:
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

    fields_ok, fields_copied = await _transfer_lead_fields(
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
    if not (chat_ok and contact_ok and failed_tasks == 0 and note_ok and fields_ok):
        fail_reason = (
            f"transfer_failed(chat={chat_ok},contact={contact_ok},failed_tasks={failed_tasks},"
            f"note={note_ok},fields={fields_ok})"
        )
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
    logger.info(
        "[TG-MERGE] %s: #%s -> #%s (phone=+%s, tasks=%s, fields=%s)",
        final_status, decision.source_lead_id, decision.target_lead_id, phone, migrated_tasks, fields_copied,
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
    """Atomically claim source_lead_id and apply PairDecision with zero data loss."""
    if decision.action not in {"merge", "link_only", "conflict"}:
        return "skipped"

    # Lock source AND target (sorted, deduped) so two duplicates merging into the
    # same target cannot race on the fill-only field transfer.
    lead_ids = sorted({int(decision.source_lead_id), int(decision.target_lead_id)})
    locks = [_LEAD_LOCKS.setdefault(lid, asyncio.Lock()) for lid in lead_ids]
    async with contextlib.AsyncExitStack() as stack:
        for lead_lock in locks:
            await stack.enter_async_context(lead_lock)
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
