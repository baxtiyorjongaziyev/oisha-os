"""Tracked, bounded Lead CAPI dispatch and durable recovery outside the routing lock."""
from __future__ import annotations

import asyncio
import logging

from src.services.core.instagram import leadgen_capi_outbox as outbox
from src.services.core.marketing import meta_capi_store as store, meta_capi_triggers as triggers

logger = logging.getLogger(__name__)
_MAX_IN_FLIGHT = 4
_in_flight: dict[str, asyncio.Task] = {}
_recovery_task: asyncio.Task | None = None


def is_enabled() -> bool:
    return triggers.is_enabled()


def schedule_lead_event(leadgen_id: str, lead_id: int, phone: str = "", email: str = "") -> None:
    """Checkpoint must already contain durable intent; excess work stays queued."""
    if not is_enabled() or leadgen_id in _in_flight or len(_in_flight) >= _MAX_IN_FLIGHT:
        return
    task = asyncio.create_task(_deliver(leadgen_id, int(lead_id), phone, email))
    _in_flight[leadgen_id] = task
    task.add_done_callback(lambda done: _finished(leadgen_id, done))


def _finished(leadgen_id: str, task: asyncio.Task) -> None:
    _in_flight.pop(leadgen_id, None)
    if not task.cancelled() and task.exception() is not None:
        logger.warning("[META CAPI] Background dispatch failed: %s", type(task.exception()).__name__)


async def _deliver(leadgen_id: str, lead_id: int, phone: str, email: str) -> None:
    try:
        result = await triggers.on_lead_created(leadgen_id, lead_id, phone=phone, email=email)
        sent = result is not None and result.status == "sent"
        if result is not None and result.status == "duplicate":
            sent = await store.get_event_status(leadgen_id, "Lead") == "sent"
        if sent:
            await asyncio.to_thread(outbox.complete, leadgen_id)
        else:
            await asyncio.to_thread(outbox.retry_later, leadgen_id)
    except Exception as exc:
        logger.warning("[META CAPI] Lead dispatch failed: %s", type(exc).__name__)
        await asyncio.to_thread(outbox.retry_later, leadgen_id)


def schedule_capi_recovery() -> None:
    """Called every watchdog tick, even when all three delivery channels are complete."""
    global _recovery_task
    if not is_enabled() or (_recovery_task is not None and not _recovery_task.done()):
        return
    _recovery_task = asyncio.create_task(_recover())


async def _legacy_failed_events(limit: int) -> list[dict]:
    """Recover failures recorded before durable intent was added; no historical backfill."""
    await store.ensure_table()
    stale_before = (store._now() - store._STALE_PENDING).isoformat()
    return await store._pool().execute(
        "SELECT leadgen_id, amo_lead_id AS lead_id FROM capi_events "
        "WHERE event_name = 'Lead' AND amo_lead_id IS NOT NULL "
        "AND (status = 'failed' OR (status = 'pending' AND updated_at < ?)) "
        "ORDER BY updated_at LIMIT ?",
        [stale_before, limit],
    )


async def _recover() -> None:
    try:
        rows = await asyncio.to_thread(outbox.pending, _MAX_IN_FLIGHT)
        dispatched = set(_in_flight) | {row["leadgen_id"] for row in rows}
        for row in rows:
            schedule_lead_event(row["leadgen_id"], row["lead_id"])
        slots = _MAX_IN_FLIGHT - len(_in_flight)
        if slots <= 0:
            return
        for row in await _legacy_failed_events(20):
            if row["leadgen_id"] in dispatched:
                continue
            await asyncio.to_thread(outbox.enqueue, row["leadgen_id"], row["lead_id"])
    except Exception as exc:
        logger.warning("[META CAPI] Recovery scan failed: %s", type(exc).__name__)
