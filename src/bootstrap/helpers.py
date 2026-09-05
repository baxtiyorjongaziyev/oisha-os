"""
Bootstrap helper functions for surgical commands and message processing.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("OishaBootstrap")


def _negotiation_int(val: Any) -> int:
    if val is None:
        return 0
    try:
        return int(float(str(val).replace(" ", "")))
    except (ValueError, TypeError):
        return 0


async def _command_processor(event: Any, handler_coro: Any) -> None:
    """Standardized handler wrapper for private commands."""
    sender = await event.get_sender()
    sender_id = getattr(sender, "id", None)
    first_name = getattr(sender, "first_name", "") or ""
    last_name = getattr(sender, "last_name", "") or ""
    user_name = f"{first_name} {last_name}".strip() or "User"

    logger.info(
        f"[BOOT COMMAND] Processing command from {user_name} ({sender_id})"
    )
    try:
        await handler_coro(event)
    except Exception as e:
        logger.error(
            f"[BOOT COMMAND] Error in command execution: {e}",
            exc_info=True,
        )
        try:
            await event.reply(
                "❌ Buyruqni bajarishda xatolik yuz berdi. Iltimos qaytadan urinib ko'ring."
            )
        except Exception:
            pass


async def _surgical_send(msg: str) -> None:
    from src.context import app_ctx
    if app_ctx.bot_client:
        await app_ctx.bot_client.send_message("me", msg)
