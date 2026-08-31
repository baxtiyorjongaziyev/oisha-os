"""
CRM and task scheduling jobs mixin for background monitor.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.schedulers.bg_monitor.helpers import _env_enabled

logger = logging.getLogger("BackgroundMonitor")


class JobsCrmMixin:
    """CRM, stagnation, deadline, and daily/weekly report jobs."""

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
        
        # Filtr funksiya ichida (soat + atomik DB claim). Tashqi minute oynasi
        # olib tashlandi — u main_loop scheduler bilan birga takror yuborishga
        # yo'l ochardi. check_airtable_deadlines() o'zi kuniga bir marta ishlaydi.
        await check_airtable_deadlines()

    async def _job_check_amocrm_due_tasks(self) -> None:
        """AmoCRM da muddati kelgan va kechikkan vazifalarni guruh follow-up mavzusiga yo'llash."""
        try:
            from src.services.core.amocrm_task_notifier import AmoCrmTaskNotifier

            amocrm_client = self._get_amocrm_client()
            if amocrm_client and self.bot_client:
                notifier = AmoCrmTaskNotifier(
                    amocrm=amocrm_client,
                    db=self._get_db(),
                    bot_runtime=self.bot_client,
                )
                await notifier.check_and_notify_due_tasks()
        except Exception as exc:
            logger.error("[TASK_NOTIFIER] Error checking due tasks: %s", exc)

    async def _job_lead_os_cycle(self, now: datetime) -> None:
        from src.services.core.leads.lead_operating_system import LeadOperatingSystem

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
                        report_html = f"📊 <b>KUNLIK HISOBOT</b>\n\n{report}"
                        fin_group = getattr(self.settings, "HISOBCHI_FINANCE_GROUP_ID", None) if self.settings else None
                        pnl_topic = getattr(self.settings, "HISOBCHI_PNL_TOPIC_ID", None) if self.settings else None
                        if fin_group:
                            send_kwargs = {"parse_mode": "html"}
                            if pnl_topic:
                                send_kwargs["reply_to"] = pnl_topic
                            if self.bot_client:
                                try:
                                    bot_kwargs = {"parse_mode": "html"}
                                    if pnl_topic:
                                        bot_kwargs["message_thread_id"] = pnl_topic
                                    await self.bot_client.send_message(fin_group, report_html, **bot_kwargs)
                                    delivered = True
                                    logger.info("[SCHEDULE] Daily EnterpriseReport sent via bot.")
                                except Exception as b_exc:
                                    logger.warning("[SCHEDULE][REPORT] bot_client failed: %s", b_exc)
                            if not delivered:
                                await self._notify_admin(report_html, parse_mode="html")
                        else:
                            await self._notify_admin(report_html, parse_mode="html")
                            logger.info("[SCHEDULE] Daily EnterpriseReport sent to admin.")
            except Exception as exc:
                logger.error("[SCHEDULE][REPORT] Error: %s", exc)
            self._mark_sent(key)

    async def _job_crm_daily_report(self, now: datetime) -> None:
        key = self._job_key("crm_daily_report", now)
        if not self._already_sent(key):
            try:
                from src.services.core.crm.crm_daily_report import CRMDailyReporter

                amocrm_client = self._get_amocrm_client()
                if amocrm_client:
                    reporter = CRMDailyReporter(amocrm=amocrm_client)
                    stats = await reporter.fetch_stats()
                    prev = reporter._load_prev_stats()
                    report_text = reporter.format_report(stats, prev)

                    send_kwargs = {}
                    if self.settings and getattr(self.settings, "TOPIC_REPORTS_ID", None):
                        send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
                    await self._send_to_group_or_admin(report_text, **send_kwargs)
                    logger.info("[SCHEDULE] CRM Daily reportagram sent.")
            except Exception as exc:
                logger.error("[SCHEDULE][CRM_REPORT] Error: %s", exc)
            self._mark_sent(key)

    async def _job_hisobchi_daily_roast(self, now: datetime) -> None:
        key = self._job_key("hisobchi_daily_roast", now)
        if not self._already_sent(key):
            try:
                if self.hisobchi_analyst:
                    period = now.strftime("%Y-%m")
                    roast_text = await self.hisobchi_analyst.analyze_month(period)
                    
                    send_kwargs = {}
                    if self.settings and getattr(self.settings, "TOPIC_REPORTS_ID", None):
                        send_kwargs["reply_to"] = self.settings.TOPIC_REPORTS_ID
                    
                    # Alternatively, if there is a finance group, it could be sent there.
                    # But reports topic is standard for BackgroundMonitor.
                    await self._send_to_group_or_admin(roast_text, **send_kwargs)
                    logger.info("[SCHEDULE] Hisobchi daily roast sent.")
                else:
                    logger.warning("[SCHEDULE] hisobchi_analyst not available for daily roast.")
            except Exception as exc:
                logger.error("[SCHEDULE][HISOBCHI_ROAST] Error: %s", exc)
            self._mark_sent(key)

    async def _job_crm_weekly_report(self, now: datetime) -> None:
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter, previous_week_range

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
                if self.settings and getattr(self.settings, "TOPIC_REPORTS_ID", None):
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
                            if self.bot_client:
                                try:
                                    bot_kwargs = {}
                                    if target_topic:
                                        bot_kwargs["message_thread_id"] = target_topic
                                    await self.bot_client.send_message(target_group, alert, **bot_kwargs)
                                    delivered = True
                                    logger.info("[SCHEDULE] Stagnation alert sent to group %s via bot.", target_group)
                                except Exception as b_exc:
                                    logger.warning("[SCHEDULE][STAGNATION] bot_client failed: %s", b_exc)
                            if not delivered:
                                await self._notify_admin(alert)
                        else:
                            await self._notify_admin(alert)
                            logger.info("[SCHEDULE] Stagnation alert sent to admin.")
            except Exception as exc:
                logger.error("[SCHEDULE][STAGNATION] Error: %s", exc)
            self._mark_sent(key)
