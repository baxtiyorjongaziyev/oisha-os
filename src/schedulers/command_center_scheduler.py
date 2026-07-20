"""Scheduled Oisha command center digest delivery."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from src.services.core.admin_command_router import build_command_center_response
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime

logger = logging.getLogger(__name__)

SnapshotProvider = Callable[[], Awaitable[dict[str, Any]]]


def _as_bot_runtime(bot_client: Any) -> BotRuntimePort | None:
    if bot_client is None:
        return None
    if hasattr(bot_client, "backend") and hasattr(bot_client, "send_message"):
        return bot_client
    return TelethonBotRuntime(bot_client)


async def send_command_center_digest(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    snapshot_provider: SnapshotProvider,
    topic_id: Optional[int] = None,
) -> bool:
    """Send one read-only command center digest through the bot account."""
    bot_runtime = _as_bot_runtime(bot_client)
    if bot_runtime is None or not target_chat_id:
        logger.info("[COMMAND_CENTER] Digest skipped: bot or target chat missing.")
        return False

    try:
        payload = await snapshot_provider()
        response = build_command_center_response(payload)
        await bot_runtime.send_message(
            target_chat_id,
            response.text,
            parse_mode=response.parse_mode,
            message_thread_id=topic_id,
            disable_web_page_preview=True,
        )
        logger.info("[COMMAND_CENTER] Digest sent to %s.", target_chat_id)
        return True
    except Exception:
        logger.error("[COMMAND_CENTER] Digest failed.", exc_info=True)
        return False


async def command_center_digest_loop(
    *,
    bot_client: Any,
    target_chat_id: int | str | None,
    snapshot_provider: SnapshotProvider,
    hour: int = 9,
    minute: int = 5,
    topic_id: Optional[int] = None,
) -> None:
    """Run a daily command center digest loop on the server runtime."""
    from src.time_utils import get_local_now

    await asyncio.sleep(10)
    logger.info("[COMMAND_CENTER] Daily digest loop started.")
    last_run_date: str | None = None

    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if (
                now.hour == int(hour)
                and now.minute == int(minute)
                and last_run_date != today
            ):
                sent = await send_command_center_digest(
                    bot_client=bot_client,
                    target_chat_id=target_chat_id,
                    snapshot_provider=snapshot_provider,
                    topic_id=topic_id,
                )
                if sent:
                    last_run_date = today
        except Exception:
            logger.error("[COMMAND_CENTER] Loop error.", exc_info=True)
        await asyncio.sleep(30)
