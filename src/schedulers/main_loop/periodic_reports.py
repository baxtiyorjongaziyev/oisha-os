"""
Daily and weekly scheduled reporting jobs (CRM report, hisobchi roast, stagnation).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.settings import settings
import src.main as m
from src.schedulers.main_loop.helpers import _is_due

logger = logging.getLogger("OishaScheduler")


def _is_job_sent(task: Any, key: str) -> bool:
    if not hasattr(task, "_sent_jobs"):
        task._sent_jobs = set()
    if key in task._sent_jobs:
        return True
    task._sent_jobs.add(key)
    return False


async def _check_overdue_and_status(now: datetime, task: Any) -> None:
    today_str = now.strftime("%Y-%m-%d")
    if _is_due(now, 17, 0) and not _is_job_sent(task, f"overdue_nudges_{today_str}"):
        try:
            from src.services.core.proactive_worker import send_overdue_nudges
            await send_overdue_nudges()
        except Exception as exc:
            logger.error("[SCHEDULE][OVERDUE] Error: %s", exc)

    if any(_is_due(now, h, 0) for h in [13, 17, 21]):
        job_key = f"status_notify_{now.hour}_{today_str}"
        if not _is_job_sent(task, job_key) and m.client:
            await m.notify_admin(
                "👸 **Oisha OS: Tizim nazoratda**\nAmoCRM, Airtable va Lead-Scraper barqaror ishlamoqda.",
                m.client,
            )


async def _check_morning_jobs(now: datetime, task: Any) -> None:
    today_str = now.strftime("%Y-%m-%d")
    if now.weekday() == 4 and _is_due(now, 9, 0) and not _is_job_sent(task, f"juma_notifier_{today_str}"):
        try:
            if m.juma_notifier:
                await m.juma_notifier.check_and_send()
                logger.info("[SCHEDULE] JumaNotifier sent.")
        except Exception as juma_exc:
            logger.error("[SCHEDULE][JUMA] Error: %s", juma_exc)

    if _is_due(now, 9, 0) and not _is_job_sent(task, f"auto_briefing_{today_str}"):
        try:
            if getattr(m, "admin_bot", None):
                await m.admin_bot.run_auto_briefing()
                logger.info("[SCHEDULE] Auto-briefing sent.")
        except Exception as exc:
            logger.error("[SCHEDULE][AUTO-BRIEFING] Error: %s", exc)

    if _is_due(now, 9, 30) and not _is_job_sent(task, f"surgical_missions_{today_str}"):
        try:
            from src.services.core.mission_control import MissionControl
            mc = MissionControl(db=m.msg_controller.db if m.msg_controller else None)
            managers = await mc.get_manager_list()
            if managers:
                await mc.distribute_missions(managers)
        except Exception as mc_exc:
            logger.error("[SCHEDULE][MISSIONS] Error: %s", mc_exc)


async def _check_daily_reports(now: datetime, task: Any) -> None:
    today_str = now.strftime("%Y-%m-%d")
    if _is_due(now, 18, 0) and not _is_job_sent(task, f"daily_report_{today_str}"):
        try:
            if m.msg_controller:
                report = await m.msg_controller.enterprise_reporter.get_daily_efficiency_report()
                if report:
                    bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                    fin_group = settings.HISOBCHI_FINANCE_GROUP_ID
                    if fin_group and bot_rt:
                        kw = {"parse_mode": "html"}
                        if settings.HISOBCHI_PNL_TOPIC_ID:
                            kw["message_thread_id"] = settings.HISOBCHI_PNL_TOPIC_ID
                        await bot_rt.send_message(fin_group, f"📊 <b>KUNLIK HISOBOT</b>\n\n{report}", **kw)
        except Exception as rep_exc:
            logger.error("[SCHEDULE][REPORT] Error: %s", rep_exc)

    if _is_due(now, 19, 30) and not _is_job_sent(task, f"crm_daily_report_{today_str}"):
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter
            from src.services.core.crm.crm_service import CRMService
            crm = CRMService()
            if crm.amocrm:
                reporter = CRMDailyReporter(amocrm=crm.amocrm)
                stats = await reporter.fetch_stats()
                prev = reporter._load_prev_stats()
                report_text = reporter.format_report(stats, prev)
                target_group = m.TN5_GROUP_ID or getattr(settings, "CRM_GROUP_ID", None)
                bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                if target_group and bot_rt:
                    kw = {"message_thread_id": settings.TOPIC_REPORTS_ID} if settings.TOPIC_REPORTS_ID else {}
                    await bot_rt.send_message(target_group, report_text, **kw)
        except Exception as rep_exc:
            logger.error("[SCHEDULE][CRM_REPORT] Error: %s", rep_exc)


async def _check_weekly_and_stagnation(now: datetime, task: Any) -> None:
    today_str = now.strftime("%Y-%m-%d")
    if (
        now.weekday() == 0
        and _is_due(now, 9, 0)
        and not _is_job_sent(task, f"crm_weekly_report_{today_str}")
    ):
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter
            from src.services.core.crm.crm_service import CRMService
            crm = CRMService()
            if crm.amocrm:
                reporter = CRMDailyReporter(amocrm=crm.amocrm)
                report_text = await reporter.get_weekly_report()
                bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                target_group = m.TN5_GROUP_ID or getattr(settings, "CRM_GROUP_ID", None)
                if target_group and bot_rt:
                    kw = {"message_thread_id": settings.TOPIC_REPORTS_ID} if settings.TOPIC_REPORTS_ID else {}
                    await bot_rt.send_message(target_group, report_text, **kw)
        except Exception as exc:
            logger.error("[SCHEDULE][WEEKLY_CRM] Error: %s", exc)

    if (
        _is_due(now, 10, 0) or _is_due(now, 22, 0)
    ) and not _is_job_sent(task, f"stagnation_{now.hour}_{today_str}"):
        try:
            from src.services.proactive.stagnation import check_amocrm_stagnation
            await check_amocrm_stagnation()
        except Exception as exc:
            logger.error("[SCHEDULE][STAGNATION] Error: %s", exc)


async def run_periodic_reports(now: datetime, background_monitor_task: Any) -> None:
    """Entry point for periodic reporting checks executed in the scheduler loop."""
    await _check_overdue_and_status(now, background_monitor_task)
    await _check_morning_jobs(now, background_monitor_task)
    await _check_daily_reports(now, background_monitor_task)
    await _check_weekly_and_stagnation(now, background_monitor_task)
