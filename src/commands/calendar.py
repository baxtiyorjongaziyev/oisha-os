"""Calendar scan command."""
from __future__ import annotations

import logging

from src.commands import register_command

logger = logging.getLogger(__name__)


@register_command("/calendar_scan")
async def cmd_calendar_scan(event, **ctx):
    meeting_scheduler = ctx["meeting_scheduler"]
    client = ctx["client"]
    _negotiation_int = ctx["_negotiation_int"]

    if not meeting_scheduler:
        await event.respond("❌ Calendar scanner hali ishga tushmagan.")
        return
    await event.respond("📅 Telegram chatlardan uchrashuvlarni qidiryapman...")
    try:
        result = await meeting_scheduler.scan_recent_dialogs(
            client,
            dialog_limit=_negotiation_int("CALENDAR_SCAN_DIALOG_LIMIT", 80),
            message_limit=_negotiation_int("CALENDAR_SCAN_MESSAGE_LIMIT", 12),
            max_age_hours=_negotiation_int("CALENDAR_SCAN_MAX_AGE_HOURS", 72),
        )
        await event.respond(
            "📅 Calendar scan yakunlandi:\n"
            f"Tekshirildi: {result.get('scanned', 0)} chat\n"
            f"Yaratildi: {result.get('created', 0)} uchrashuv\n"
            f"Eski/noaniq o'tkazildi: {result.get('skipped_old', 0)}\n"
            f"Xato: {result.get('errors', 0)}"
        )
    except Exception as exc:
        logger.error(f"[COMMAND] /calendar_scan error: {exc}", exc_info=True)
        await event.respond(f"❌ Calendar scan xatosi: {type(exc).__name__}")
