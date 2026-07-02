"""ERP commands for finance, team, and projects."""
from __future__ import annotations

import logging

from src.commands import register_command

logger = logging.getLogger(__name__)


@register_command("/erp", "/moliya", "/jamoa", "/loyihalar", "/loyiha_qosh", "/xarajat")
async def cmd_erp(event, **ctx):
    msg_controller = ctx["msg_controller"]
    cmd = event.message.text.lower().strip()

    try:
        from src.services.core.finance.erp_handlers import (
            cmd_erp_holat, cmd_moliya, cmd_jamoa, cmd_loyihalar,
            cmd_erp_salomatlik, cmd_qo_shish_loyiha, cmd_xarajat_qosh,
            ERP_HELP_TEXT,
        )
        db = msg_controller.db

        if cmd.startswith("/erp_holat"):
            await cmd_erp_holat(event, db)
        elif cmd.startswith("/erp_salomatlik"):
            await cmd_erp_salomatlik(event, db)
        elif cmd.startswith("/moliya"):
            parts = cmd.split()
            period = parts[1] if len(parts) > 1 else None
            await cmd_moliya(event, db, period)
        elif cmd.startswith("/jamoa"):
            parts = cmd.split()
            period = parts[1] if len(parts) > 1 else None
            await cmd_jamoa(event, db, period)
        elif cmd.startswith("/loyiha_qosh"):
            args = cmd[len("/loyiha_qosh"):].strip().split("|")
            if len(args) >= 4:
                try:
                    budget = int(args[2].strip())
                except ValueError:
                    await event.respond("❌ Byudjet raqam bo'lishi kerak. Namuna: /loyiha_qosh Sarlavha | Mijoz | 5000000 | 2025-07-01")
                    return
                await cmd_qo_shish_loyiha(event, db, args[0].strip(), args[1].strip(),
                                          budget, args[3].strip())
            else:
                await event.respond("❌ Format: /loyiha_qosh Sarlavha | Mijoz | Byudjet | Muddat")
        elif cmd.startswith("/xarajat"):
            args = cmd[len("/xarajat"):].strip().split("|")
            if len(args) >= 3:
                try:
                    amount = int(args[2].strip())
                except ValueError:
                    await event.respond("❌ Miqdor raqam bo'lishi kerak. Namuna: /xarajat ofis | Printer qog'oz | 150000")
                    return
                await cmd_xarajat_qosh(event, db, args[0].strip(), args[1].strip(), amount)
            else:
                await event.respond("❌ Format: /xarajat kategoriya | tavsif | miqdor")
        elif cmd.startswith("/loyihalar"):
            await cmd_loyihalar(event, db)
        elif cmd == "/erp_help":
            await event.respond(ERP_HELP_TEXT, parse_mode="markdown")
        elif cmd.startswith("/erp"):
            await cmd_erp_holat(event, db)
    except Exception as e:
        logger.error(f"[ERP COMMAND] {cmd} error: {e}", exc_info=True)
        await event.respond(f"❌ ERP xatolik: {e}")
