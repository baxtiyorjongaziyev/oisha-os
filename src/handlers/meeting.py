"""Meeting scheduler handler."""
from __future__ import annotations

import logging

from src.context import app_ctx

logger = logging.getLogger(__name__)


async def meeting_scheduler_handler(event):
    """Create Google Calendar events from clear Telegram meeting agreements."""
    if not app_ctx.meeting_scheduler:
        return
    try:
        await app_ctx.meeting_scheduler.process_event(event, app_ctx.client)
    except Exception as exc:
        logger.warning(f"[MEETING] Scheduler skipped: {type(exc).__name__}: {exc}")
