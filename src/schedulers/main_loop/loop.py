"""
Continuous background monitoring scheduler loop orchestrator.
"""
from __future__ import annotations

import asyncio
import logging

from src.time_utils import get_local_now, is_quiet_hours
from src.schedulers.main_loop.crm_and_tasks import run_stagnation_and_tasks
from src.schedulers.main_loop.periodic_reports import run_periodic_reports
from src.schedulers.main_loop.coaching_and_mindset import run_coaching_and_mindset

logger = logging.getLogger("OishaScheduler")


async def background_monitor_task() -> None:
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish (AmoCRM + Airtable).

    Runs indefinitely with 5-minute intervals between checks.
    Handles errors gracefully and continues operation.
    """
    logger.info("[MONITOR] Boshlandi (Interval: 5 daqiqa)")

    while True:
        try:
            now = get_local_now()

            # _sent_jobs kalitlari sana bilan tugaydi — kun almashganda eski
            # kalitlarni tozalaymiz (aks holda to'plam cheksiz o'sadi)
            _today = now.strftime("%Y-%m-%d")
            if getattr(background_monitor_task, "_sent_jobs_day", None) != _today:
                background_monitor_task._sent_jobs = set()
                background_monitor_task._sent_jobs_day = _today

            if is_quiet_hours(now):
                logger.debug(
                    "[MONITOR] Quiet hours active. Automatic notifications are paused."
                )
                await asyncio.sleep(300)
                continue

            await run_stagnation_and_tasks(now, background_monitor_task)
            await run_periodic_reports(now, background_monitor_task)
            await run_coaching_and_mindset(now, background_monitor_task)

        except Exception as e:
            logger.error("[MONITOR] Xatolik: %s", e, exc_info=True)

        await asyncio.sleep(300)
