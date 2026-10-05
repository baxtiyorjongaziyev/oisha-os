"""Har dushanba 09:15 (Toshkent) Meta app health-check hisobotini Owner'ga yuboradi."""
from __future__ import annotations

import asyncio
import logging
import os

from src.services.core.instagram.meta_health_check import MetaHealthCheck, format_report

logger = logging.getLogger(__name__)

RUN_WEEKDAY, RUN_HOUR, RUN_MINUTE = 0, 9, 15


def _enabled() -> bool:
    return os.getenv("META_HEALTH_CHECK_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


async def send_meta_health_report(bot_client=None, chat_id=None) -> str:
    from src.settings import settings

    report = format_report(await MetaHealthCheck().run())
    target = chat_id or getattr(settings, "OWNER_ID", 0)
    if bot_client and target:
        try:
            await bot_client.send_message(target, report, parse_mode="html")
        except Exception as exc:
            logger.error("[META-HEALTH] Telegram send failed: %s", exc)
    return report


async def meta_health_check_loop(bot_client) -> None:
    from src.time_utils import get_local_now

    await asyncio.sleep(120)
    last_run_week: str | None = None
    while True:
        try:
            now = get_local_now()
            iso = now.isocalendar()
            week_key = f"{iso.year}-{iso.week}"
            due = (now.weekday(), now.hour, now.minute) == (RUN_WEEKDAY, RUN_HOUR, RUN_MINUTE)
            if due and last_run_week != week_key:
                last_run_week = week_key
                if not _enabled():
                    logger.info("[META-HEALTH] META_HEALTH_CHECK_ENABLED=0 — skipped")
                elif not MetaHealthCheck().configured:
                    logger.info("[META-HEALTH] Skipped: META_PAGE_ACCESS_TOKEN not configured")
                else:
                    await send_meta_health_report(bot_client=bot_client)
        except Exception as exc:
            logger.error("[META-HEALTH] Loop error: %s", exc)
        await asyncio.sleep(30)
