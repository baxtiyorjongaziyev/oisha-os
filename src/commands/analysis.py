"""Call analysis command."""
from __future__ import annotations

import logging

from src.commands import register_command

logger = logging.getLogger(__name__)


@register_command("/tahlil")
async def cmd_tahlil(event, **ctx):
    msg_controller = ctx["msg_controller"]
    bot_client = ctx["bot_client"]
    settings = ctx["settings"]

    await event.respond("⏳ So'nggi qo'ng'iroqlar tahlil qilinmoqda...")
    try:
        from src.services.core.call_analyzer import CallAnalyzer
        parts = event.message.text.lower().strip().split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
        analyzer = CallAnalyzer(
            amocrm=msg_controller.crm.amocrm,
            db=msg_controller.db,
        )
        result = await analyzer.analyze_recent_calls(limit=limit, write=True)
        if isinstance(result, dict):
            analyzed = result.get("calls_processed", 0)
            total = result.get("leads_scanned", 0)
            await event.respond(
                f"✅ {analyzed}/{total} qo'ng'iroq tahlil qilindi.\n"
                f"AmoCRM ga primicheniya qo'shildi."
            )
        else:
            await event.respond(f"✅ Tahlil tugadi: {result}")
    except Exception as e:
        logger.error(f"[COMMAND] /tahlil error: {e}", exc_info=True)
        await event.respond(f"❌ Tahlil xatoligi: {e}")
