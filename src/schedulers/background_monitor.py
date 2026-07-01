"""
Background monitor — barcha korporativ monitoring vazifalari.

Usage:
    from src.schedulers.background_monitor import BackgroundMonitor
    monitor = BackgroundMonitor(msg_controller=..., client=..., ...)
    asyncio.create_task(monitor.run())
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional, Set

logger = logging.getLogger(__name__)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


class BackgroundMonitor:
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish."""

    def __init__(
        self,
        *,
        msg_controller: Any,
        client: Any,
        juma_notifier: Any = None,
        settings: Any = None,
        get_surgical_integration: Any = None,
        TN5_GROUP_ID: Optional[int] = None,
    ) -> None:
        self.msg_controller = msg_controller
        self.client = client
        self.juma_notifier = juma_notifier
        self.settings = settings
        self.get_surgical_integration = get_surgical_integration
        self.TN5_GROUP_ID = TN5_GROUP_ID

        self._sent_jobs: Set[str] = set()
        self._lead_os: Any = None
        self._lead_cycle_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _job_key(self, prefix: str, now: datetime, suffix: str = "") -> str:
        today = now.strftime("%Y-%m-%d")
        return f"{prefix}_{today}" + (f"_{suffix}" if suffix else "")

    def _hour_key(self, prefix: str, now: datetime) -> str:
        return f"{prefix}_{now.hour}_{now.strftime('%Y-%m-%d')}"

    def _already_sent(self, key: str) -> bool:
        return key in self._sent_jobs

    def _mark_sent(self, key: str) -> None:
        self._sent_jobs.add(key)

    async def _notify_admin(self, message: str) -> None:
        try:
            await self.client.send_message("me", message)
        except Exception as exc:
            logger.error("[NOTIFY ERROR] %s", exc)

    async def _send_to_group_or_admin(self, text: str, **kwargs) -> None:
        if self.TN5_GROUP_ID:
            await self.client.send_message(self.TN5_GROUP_ID, text, **kwargs)
        else:
            await self._notify_admin(text)

    def _get_amocrm_client(self) -> Any:
        if self.msg_controller and getattr(self.msg_controller, "crm", None):
            client = getattr(self.msg_controller.crm, "amocrm", None)
            if client:
                return client
        if self.get_surgical_integration:
            return self.get_surgical_integration().amocrm
        return None

    # ------------------------------------------------------------------
    # Scheduled jobs
    # ------------------------------------------------------------------

    async def _job_check_stagnation_and_deadlines(self) -> None:
        from src.services.core.proactive_worker import (
            check_amocrm_stagnation,
            check_airtable_deadlines,
            check_airtable_stagnation,
            check_client_journey_excellence,
        )

        await check_amocrm_stagnation()
        await check_airtable_stagnation()
        await check_client_journey_excellence()
        await check_airtable_deadlines()

    async def _job_lead_os_cycle(self, now: datetime) -> None:
        from src.services.core.lead_operating_system import LeadOperatingSystem

        if not self.msg_controller:
            return

        if self._lead_os is None:
            self._lead_os = LeadOperatingSystem(
                self.msg_controller, self.msg_controller.db
            )

        if not self._lead_cycle_at or (now - self._lead_cycle_at).total_seconds() >= 900:
            await self._lead_os.review_recent_active_leads(
                limit=12, lookback_hours=72, execute_actions=True
            )
            self._lead_cycle_at = now

        if now.hour in [10, 14, 18, 22] and now.minute == 0:
            key = self._hour_key("lead_reengagement", now)
            if not self._already_sent(key):
                await self._lead_os.run_reengagement_cycle(limit=8)
                self._mark_sent(key)

    async def _job_overdue_nudges(self, now: datetime) -> None:
        from src.services.core.proactive_worker import send_overdue_nudges

        key = self._job_key("overdue_nudges", now)
        if not self._already_sent(key):
            await send_overdue_nudges()
            self._mark_sent(key)

    async def _job_status_notify(self, now: datetime) -> None:
        key = self._hour_key("status_notify", now)
        if not self._already_sent(key):
            await self._notify_admin(
                "👸 **Oisha OS: Tizim nazoratda**\n"
                "AmoCRM, Airtable va Lead-Scraper barqaror ishlamoqda."
            )
            self._mark_sent(key)

    async def _job_juma_notifier(self, now: datetime) -> None:
        key = self._job_key("juma_notifier", now)
        if not self._already_sent(key):
            try:
                if self.juma_notifier:
                    await self.juma_notifier.check_and_send()
                    logger.info("[SCHEDULE] JumaNotifier sent.")
                else:
                    logger.warning("[SCHEDULE] JumaNotifier not initialized, skipping.")
            except Exception as exc:
                logger.error("[SCHEDULE][JUMA] Error: %s", exc)
            self._mark_sent(key)

    async def _job_surgical_missions(self, now: datetime) -> None:
        key = self._job_key("surgical_missions", now)
        if not self._already_sent(key):
            try:
                from src.services.core.mission_control import MissionControl

                mc = MissionControl(db=self.msg_controller.db if self.msg_controller else None)
                managers = await mc.get_manager_list()
                if managers:
                    await mc.distribute_missions(managers)
                    logger.info("[SCHEDULE] Surgical Missions distributed to %d managers.", len(managers))
                else:
                    logger.warning("[SCHEDULE] No managers found for mission distribution.")
            except Exception as exc:
                logger.error("[SCHEDULE][MISSIONS] Error: %s", exc)
            self._mark_sent(key)

    async def _job_daily_report(self, now: datetime) -> None:
        key = self._job_key("daily_report", now)
        if not self._already_sent(key):
            try:
                if self.msg_controller:
                    report = await self.msg_controller.enterprise_reporter.get_daily_efficiency_report()
                    if report:
                        await self._notify_admin(f"📊 **KUNLIK HISOBOT**\n\n{report}")
                        logger.info("[SCHEDULE] Daily EnterpriseReport sent.")
            except Exception as exc:
                logger.error("[SCHEDULE][REPORT] Error: %s", exc)
            self._mark_sent(key)

    async def _job_crm_daily_report(self, now: datetime) -> None:
        key = self._job_key("crm_daily_report", now)
        if not self._already_sent(key):
            try:
                from src.services.core.crm_daily_report import CRMDailyReporter

                amocrm_client = self._get_amocrm_client()
                if amocrm_client:
                    reporter = CRMDailyReporter(amocrm=amocrm_client)
                    stats = await reporter.fetch_stats()
                    prev = reporter._load_prev_stats()
                    report_text = reporter.format_report(stats, prev)

                    send_kwargs = {}
                    if self.settings and self.settings.TOPIC_REPORTS_ID:
                        send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
                    await self._send_to_group_or_admin(report_text, **send_kwargs)
                    logger.info("[SCHEDULE] CRM Daily reportagram sent.")
            except Exception as exc:
                logger.error("[SCHEDULE][CRM_REPORT] Error: %s", exc)
            self._mark_sent(key)

    async def _job_crm_weekly_report(self, now: datetime) -> None:
        try:
            from src.services.core.crm_daily_report import CRMDailyReporter, previous_week_range

            period_start, period_end = previous_week_range(now.date())
            run_key = f"{period_start.isoformat()}_{period_end.isoformat()}"
            job_key = f"crm_weekly_report_{run_key}"

            if self._already_sent(job_key):
                return

            already_sent = False
            if self.msg_controller and getattr(self.msg_controller, "db", None):
                already_sent = await self.msg_controller.db.is_job_run("crm_weekly_report", run_key)

            if already_sent:
                return

            amocrm_client = self._get_amocrm_client()
            if amocrm_client:
                reporter = CRMDailyReporter(amocrm=amocrm_client)
                stats = await reporter.fetch_weekly_stats(period_start, period_end)
                report_text = reporter.format_weekly_report_uz(stats)

                send_kwargs = {}
                if self.settings and self.settings.TOPIC_REPORTS_ID:
                    send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
                await self._send_to_group_or_admin(report_text, **send_kwargs)

                if self.msg_controller and getattr(self.msg_controller, "db", None):
                    await self.msg_controller.db.mark_job_run("crm_weekly_report", run_key)
                self._mark_sent(job_key)
                logger.info("[SCHEDULE] CRM weekly Uzbek report sent for %s.", run_key)
            else:
                logger.warning("[SCHEDULE][CRM_WEEKLY_REPORT] AmoCRM client not ready.")
        except Exception as exc:
            logger.error("[SCHEDULE][CRM_WEEKLY_REPORT] Error: %s", exc)

    async def _job_stagnation_alert(self, now: datetime) -> None:
        key = self._hour_key("stagnation_alert", now)
        if not self._already_sent(key):
            try:
                if self.msg_controller:
                    alert = await self.msg_controller.enterprise_reporter.get_stagnant_leads_alert()
                    if alert:
                        target_group = self.settings.STAGNATION_GROUP_ID if self.settings else None
                        target_topic = self.settings.STAGNATION_TOPIC_ID if self.settings else None
                        if target_group:
                            await self.client.send_message(target_group, alert, reply_to=target_topic)
                            logger.info("[SCHEDULE] Stagnation alert sent to group %s.", target_group)
                        else:
                            await self._notify_admin(alert)
                            logger.info("[SCHEDULE] Stagnation alert sent to admin.")
            except Exception as exc:
                logger.error("[SCHEDULE][STAGNATION] Error: %s", exc)
            self._mark_sent(key)

    async def _job_heartbeat(self) -> None:
        if self.client:
            try:
                from telethon import functions
                await self.client(functions.account.UpdateStatusRequest(offline=False))
                logger.debug("[HEARTBEAT] Account status set to ONLINE")
            except Exception as exc:
                logger.warning("[HEARTBEAT] Failed to update status: %s", exc)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

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

                # 6. Surgical missions (09:30)
                if now.hour == 9 and now.minute == 30:
                    await self._job_surgical_missions(now)

                # 7. Daily report (18:00)
                if now.hour == 18 and now.minute == 0:
                    await self._job_daily_report(now)

                # 8. CRM daily report (19:30)
                if now.hour == 19 and now.minute == 30:
                    await self._job_crm_daily_report(now)

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

                # 11. Heartbeat
                await self._job_heartbeat()

                await asyncio.sleep(300)
            except Exception as exc:
                logger.error("[MONITOR ERROR] %s", exc)
                await asyncio.sleep(60)
