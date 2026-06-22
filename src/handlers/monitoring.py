"""Activity monitor and CRM callback handlers."""
from __future__ import annotations

import logging

from src.context import app_ctx

logger = logging.getLogger(__name__)


def _env_enabled(name: str) -> bool:
    import os
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def activity_monitor_handler(event):
    """Log outgoing activities for auditing."""
    if not _env_enabled("ENABLE_ACTIVITY_MONITOR"):
        return
    if app_ctx.activity_monitor:
        await app_ctx.activity_monitor.log_event(event)


async def crm_note_callback_handler(event):
    """CRM note tasdiqlash/tahrirlash inline tugmalari uchun callback handler."""
    try:
        data = event.data.decode("utf-8") if isinstance(event.data, bytes) else event.data
        if not (data.startswith("crm_approve:") or data.startswith("crm_edit:")):
            return
        from src.services.core.crm_note_approval import handle_callback
        await handle_callback(data, event)
    except Exception as e:
        logger.error(f"[CRM_CALLBACK] Xatolik: {e}", exc_info=True)


async def crm_edit_text_handler(event):
    """Captures follow-up text message after user clicked ✏️ Tahrirlash."""
    try:
        from src.services.core.crm_note_approval import pop_pending_edit, handle_callback
        approve_key = pop_pending_edit(event.sender_id)
        if not approve_key:
            return
        if event.raw_text and event.raw_text.startswith("/"):
            from src.services.core.crm_note_approval import push_pending_edit
            push_pending_edit(event.sender_id, approve_key)
            return
        edit_key = approve_key.replace("crm_approve:", "crm_edit:", 1)
        ok = await handle_callback(edit_key, event, new_text=event.raw_text)
        if ok:
            from telethon import events
            raise events.StopPropagation
    except Exception as e:
        from telethon import events
        if isinstance(e, events.StopPropagation):
            raise
        logger.error(f"[CRM_EDIT] Xatolik: {e}", exc_info=True)
