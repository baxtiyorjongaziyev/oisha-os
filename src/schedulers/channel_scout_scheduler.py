"""Telegram business channel scout background scheduler."""

from __future__ import annotations

import asyncio
import logging

from src.context import app_ctx
from src.time_utils import get_local_now

logger = logging.getLogger("ChannelScoutScheduler")


async def channel_scout_loop() -> None:
    """Scan Telegram business trainer channels 3x daily (10:00, 14:00, 18:00 Tashkent) for leads."""
    from src.services.core.channel_scheduler import daily_channel_scout

    await asyncio.sleep(120)
    scan_times = [10, 14, 18]

    while True:
        try:
            now = get_local_now()
            if now.hour in scan_times and now.minute == 0:
                logger.info("[CHANNEL-SCOUT] Starting daily scan...")
                result = await daily_channel_scout(
                    client=app_ctx.client,
                    amocrm=app_ctx.amocrm,
                    db=app_ctx.db,
                )
                logger.info(
                    "[CHANNEL-SCOUT] Scan complete: %s (%s leads)",
                    result.get("status"),
                    result.get("total_leads_extracted", 0),
                )
                await asyncio.sleep(61)
        except Exception as e:
            logger.error("[CHANNEL-SCOUT] Error in channel scout loop: %s", e)
        await asyncio.sleep(30)
