"""
Graceful drain and shutdown watcher.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.context import app_ctx

logger = logging.getLogger("OishaBootstrap")


async def graceful_drain(
    client: Any,
    bot_client: Any,
    msg_controller: Any,
    health_api_task: Any,
    m: Any,
) -> None:
    drain_deadline = 25.0
    logger.info(f"[SHUTDOWN] Draining in-flight tasks for up to {drain_deadline}s...")
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks(loop=asyncio.get_running_loop()) if t is not current and not t.done()]
    drainable = [t for t in pending if not m._is_shutdown_daemon_task(t)]
    if drainable:
        logger.info(f"[SHUTDOWN] Waiting on {len(drainable)} in-flight handler task(s).")
        done, still_pending = await asyncio.wait(drainable, timeout=drain_deadline)
        if still_pending:
            logger.warning(f"[SHUTDOWN] {len(still_pending)} task(s) exceeded drain deadline.")
    if client is not None:
        try:
            await client.disconnect()
            logger.info("[SHUTDOWN] Userbot client disconnected.")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Userbot disconnect error: {e}")
    if app_ctx.aiogram_bot_head is not None:
        try:
            await app_ctx.aiogram_bot_head.stop()
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Aiogram bot head stop error: {e}")
    elif bot_client is not None:
        try:
            await bot_client.disconnect()
            logger.info("[SHUTDOWN] Bot client disconnected.")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Bot disconnect error: {e}")
    try:
        await msg_controller.db.close()
        logger.info("[SHUTDOWN] DB closed.")
    except Exception as e:
        logger.warning(f"[SHUTDOWN] DB close error: {e}")
    await m.stop_health_check_api(health_api_task)
    logger.info("[SHUTDOWN] API server stopped.")
