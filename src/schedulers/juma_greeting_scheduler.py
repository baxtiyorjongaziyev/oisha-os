"""Har Juma Toshkent 06:00 dan Shomgacha oisha.service ichida avtomatik Juma scheduler."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from src.context import app_ctx
from src.services.core.juma_guard import (
    TASHKENT_TZ,
    JumaRateConfig,
    is_juma_send_window,
    is_quiet_hours,
    load_juma_rate_config,
)

logger = logging.getLogger("JumaScheduler")


def should_trigger_juma(now: datetime, config: JumaRateConfig) -> bool:
    """Juma kuni Toshkent vaqti bilan 06:00–17:00 oraligʻida True qaytaradi."""
    local = now.replace(tzinfo=TASHKENT_TZ) if now.tzinfo is None else now.astimezone(TASHKENT_TZ)
    return (
        local.weekday() == 4
        and is_juma_send_window(local, config)
        and not is_quiet_hours(local, config)
    )


async def juma_greeting_loop(
    bot_runtime: Any = None, *, poll_seconds: int = 60, startup_delay_seconds: int = 20
) -> None:
    """Har daqiqada Juma oynasini tekshirib JumaNotifier ni non-blocking ishga tushiradi."""
    logger.info("[JUMA-SCHEDULER] Ishga tushdi (Tashkent 06:00–17:00).")
    if startup_delay_seconds > 0:
        await asyncio.sleep(startup_delay_seconds)
    while True:
        try:
            enabled = os.getenv("ENABLE_JUMA_NOTIFIER", "").strip().lower() in {
                "1", "true", "yes", "on",
            }
            if enabled:
                config = load_juma_rate_config()
                now = datetime.now(TASHKENT_TZ)
                notifier = getattr(app_ctx, "juma_notifier", None)
                if notifier and should_trigger_juma(now, config):
                    await notifier.check_and_send()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[JUMA-SCHEDULER] Xato: %s", exc)
        await asyncio.sleep(poll_seconds)
