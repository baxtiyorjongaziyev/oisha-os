"""
BackgroundMonitor main orchestrator class composing helpers, CRM jobs, and analytics jobs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional, Set

from src.schedulers.bg_monitor.helpers import (
    BaseMonitorHelpersMixin,
)
from src.schedulers.bg_monitor.jobs_crm import JobsCrmMixin
from src.schedulers.bg_monitor.jobs_analytics import JobsAnalyticsMixin

logger = logging.getLogger("BackgroundMonitor")


class BackgroundMonitor(BaseMonitorHelpersMixin, JobsCrmMixin, JobsAnalyticsMixin):
    """
    Oisha-OS background cron tasklar monitoring servisi.
    """

    def __init__(
        self,
        *,
        msg_controller: Any,
        client: Any,
        bot_client: Any = None,
        juma_notifier: Any = None,
        settings: Any = None,
        get_surgical_integration: Any = None,
        TN5_GROUP_ID: Optional[int] = None,
    ) -> None:
        self.msg_controller = msg_controller
        self.client = client
        self.bot_client = bot_client
        self.juma_notifier = juma_notifier
        self.settings = settings
        self.get_surgical_integration = get_surgical_integration
        self.TN5_GROUP_ID = TN5_GROUP_ID

        self._sent_jobs: Set[str] = set()
        self._lead_os: Any = None
        self._lead_cycle_at: Optional[datetime] = None

    async def _run_daytime_jobs(self, now: datetime) -> None:
        """Kunduzgi davriy CRM, psixologik impuls va missiya vazifalari."""
        await self._job_check_stagnation_and_deadlines()
        await self._job_check_amocrm_due_tasks()
        await self._job_lead_os_cycle(now)

        if now.hour == 17 and now.minute == 0:
            await self._job_overdue_nudges(now)

        if now.hour in [13, 17, 21] and now.minute == 0:
            await self._job_status_notify(now)

        if now.weekday() == 4 and now.hour == 9 and now.minute == 0:
            await self._job_juma_notifier(now)

        if now.hour == 9 and 10 <= now.minute < 20:
            await self._job_psychological_mindset_boost(now)

        if now.hour == 9 and now.minute == 30:
            await self._job_surgical_missions(now)

        if now.hour in [11, 15] and 25 <= now.minute < 35:
            await self._job_sales_reluctance_automation(now)

        if (now.hour == 11 and 40 <= now.minute < 50) or (now.hour == 16 and 25 <= now.minute < 35):
            await self._job_pm_conflict_automation(now)

        if now.hour == 18 and now.minute == 0:
            await self._job_daily_report(now)

    async def run(self) -> None:
        """Barcha monitoring vazifalarini 5 daqiqalik interval bilan ishga tushirish."""
        from src.time_utils import get_local_now, is_quiet_hours

        logger.info("[MONITOR] Boshlandi (Interval: 5 daqiqa)")

        while True:
            try:
                now = get_local_now()

                if is_quiet_hours(now):
                    logger.debug("[MONITOR] Quiet hours active. Automatic notifications are paused.")
                    await asyncio.sleep(300)
                    continue

                await self._run_daytime_jobs(now)

                # Stagnation alert (10:00, 22:00)
                if now.hour in [10, 22] and now.minute == 0:
                    await self._job_stagnation_alert(now)

                # Kunlik savdo sifati hisoboti (20:00)
                if now.hour == 20 and now.minute < 5:
                    await self._job_call_quality_daily(now)

                # Haftalik: ideal skript + playbook takliflari (dushanba 10:00)
                if now.weekday() == 0 and now.hour == 10 and now.minute < 5:
                    await self._job_call_quality_weekly(now)

                # Haftalik konversiya kartochkalari (dushanba 10:05)
                if now.weekday() == 0 and now.hour == 10 and 5 <= now.minute < 10:
                    await self._job_conversion_weekly(now)

                await self._job_heartbeat()

                if now.minute == 0:
                    await self._job_auto_tasks(now)

                await asyncio.sleep(300)
            except Exception as exc:
                logger.error("[MONITOR ERROR] %s", exc, exc_info=True)
                await asyncio.sleep(60)
