"""
BackgroundMonitor main orchestrator class composing helpers, CRM jobs, and analytics jobs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set

from src.schedulers.bg_monitor.helpers import (
    BaseMonitorHelpersMixin,
    _env_enabled,
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
        hisobchi_analyst: Any = None,
    ) -> None:
        self.msg_controller = msg_controller
        self.client = client
        self.bot_client = bot_client
        self.juma_notifier = juma_notifier
        self.settings = settings
        self.get_surgical_integration = get_surgical_integration
        self.TN5_GROUP_ID = TN5_GROUP_ID
        self.hisobchi_analyst = hisobchi_analyst

        self._sent_jobs: Set[str] = set()
        self._lead_os: Any = None
        self._lead_cycle_at: Optional[datetime] = None

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

                # 1. Stagnatsiya va Deadline tekshirish
                await self._job_check_stagnation_and_deadlines()

                # 1b. AmoCRM task deadlines and overdue task notifications (Follow-up topic)
                await self._job_check_amocrm_due_tasks()

                # 2. Lead OS cycle
                await self._job_lead_os_cycle(now)

                # 3. Overdue nudges (17:00)
                if now.hour == 17 and now.minute == 0:
                    await self._job_overdue_nudges(now)

                # 4. Status notify (13:00, 17:00, 21:00)
                if now.hour in [13, 17, 21] and now.minute == 0:
                    await self._job_status_notify(now)

                # 5. Juma notifier (Friday 09:00)
                if now.weekday() == 4 and now.hour == 9 and now.minute == 0:
                    await self._job_juma_notifier(now)

                # 5b. Morning Mindset Boost (09:15)
                if now.hour == 9 and 10 <= now.minute < 20:
                    await self._job_psychological_mindset_boost(now)

                # 6. Surgical missions (09:30)
                if now.hour == 9 and now.minute == 30:
                    await self._job_surgical_missions(now)

                # 6b. Sales Reluctance Automation Sweep (11:30, 15:30)
                if now.hour in [11, 15] and 25 <= now.minute < 35:
                    await self._job_sales_reluctance_automation(now)

                # 6c. PM Conflict & Delay Automation Sweep (11:45, 16:30)
                if (now.hour == 11 and 40 <= now.minute < 50) or (now.hour == 16 and 25 <= now.minute < 35):
                    await self._job_pm_conflict_automation(now)

                # 7. Daily report (18:00)
                if now.hour == 18 and now.minute == 0:
                    await self._job_daily_report(now)

                # 8. CRM daily report (19:30)
                if now.hour == 19 and now.minute == 30:
                    await self._job_crm_daily_report(now)

                # Hisobchi daily roast (20:30)
                if now.hour == 20 and now.minute == 30:
                    await self._job_hisobchi_daily_roast(now)

                # 9. CRM weekly report (configurable)
                weekly_enabled = os.getenv("CRM_WEEKLY_REPORT_ENABLED", "true").lower() not in {
                    "0", "false", "no", "off",
                }
                weekly_weekday = int(os.getenv("CRM_WEEKLY_REPORT_WEEKDAY", "0"))
                weekly_hour = int(os.getenv("CRM_WEEKLY_REPORT_HOUR", "9"))
                weekly_minute = int(os.getenv("CRM_WEEKLY_REPORT_MINUTE", "0"))
                if (
                    weekly_enabled
                    and now.weekday() == weekly_weekday
                    and now.hour == weekly_hour
                    and now.minute == weekly_minute
                ):
                    await self._job_crm_weekly_report(now)

                # 10. Stagnation alert (10:00, 22:00)
                if now.hour in [10, 22] and now.minute == 0:
                    await self._job_stagnation_alert(now)

                # 11. Kunlik savdo sifati hisoboti (20:00)
                # Sikl har 5 daqiqada aylanadi va drift bo'ladi — `minute == 0`
                # ga tushmay ketishi mumkin. Oyna kengroq, takrorlashdan
                # `_already_sent` himoya qiladi.
                if now.hour == 20 and now.minute < 5:
                    await self._job_call_quality_daily(now)

                # 12. Haftalik: ideal skript + playbook takliflari (dushanba 10:00)
                if now.weekday() == 0 and now.hour == 10 and now.minute < 5:
                    await self._job_call_quality_weekly(now)

                # 12b. Haftalik konversiya kartochkalari (dushanba 10:05)
                if now.weekday() == 0 and now.hour == 10 and 5 <= now.minute < 10:
                    await self._job_conversion_weekly(now)

                # 13. Heartbeat
                await self._job_heartbeat()

                # 14. Auto tasks — har soat boshida
                if now.minute == 0:
                    await self._job_auto_tasks(now)

                await asyncio.sleep(300)
            except Exception as exc:
                logger.error("[MONITOR ERROR] %s", exc)
                await asyncio.sleep(60)
