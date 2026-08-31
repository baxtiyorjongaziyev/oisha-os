"""Scheduler for weekly Instagram Meta insights report."""
from __future__ import annotations

import asyncio
import logging

from src.services.core.instagram_weekly_report import InstagramWeeklyReportAgent

logger = logging.getLogger(__name__)


async def send_instagram_weekly_report(bot_client=None, team_group_id=None) -> str | None:
    result = await InstagramWeeklyReportAgent().run()
    report = result["report"]
    if bot_client and team_group_id:
        try:
            await bot_client.send_message(team_group_id, report, parse_mode="html")
        except Exception as exc:
            logger.error("[IG-WEEKLY] Telegram send failed: %s", exc)
    return report


async def instagram_weekly_report_loop(bot_client, team_group_id):
    from src.time_utils import get_local_now

    await asyncio.sleep(90)
    last_run_week: str | None = None
    while True:
        try:
            now = get_local_now()
            week_key = f"{now.isocalendar().year}-{now.isocalendar().week}"
            if now.weekday() == 0 and now.hour == 9 and now.minute == 30 and last_run_week != week_key:
                agent = InstagramWeeklyReportAgent()
                if not all(agent.credential_status().values()):
                    logger.info("[IG-WEEKLY] Scheduled report skipped: Meta credentials not configured")
                else:
                    await send_instagram_weekly_report(bot_client=bot_client, team_group_id=team_group_id)
                last_run_week = week_key
                await asyncio.sleep(61)
        except Exception as exc:
            logger.error("[IG-WEEKLY] Loop error: %s", exc)
        await asyncio.sleep(30)
