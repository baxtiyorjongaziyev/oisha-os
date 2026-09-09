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
from src.services.core.crm.daily_report.models import PeriodType

logger = logging.getLogger("OishaScheduler")


def _is_job_sent(task: Any, key: str) -> bool:
    if not hasattr(task, "_sent_jobs"):
        task._sent_jobs = set()
    if key in task._sent_jobs:
        return True
    task._sent_jobs.add(key)
    return False


def _default_period_reporter():
    from src.services.core.crm.daily_report import CRMPeriodReporter
    from src.services.core.crm.crm_service import CRMService
    crm = CRMService()
    if not crm.amocrm:
        return None
    return CRMPeriodReporter(amocrm=crm.amocrm)


async def _send_period_report(ptype, now, task, *, reporter_factory=None):
    key = f"crm_{ptype.value}_report_{now:%Y-%m-%d}"
    if _is_job_sent(task, key):
        return
    try:
        reporter = (reporter_factory or _default_period_reporter)()
        if reporter is None:
            logger.warning("[SCHEDULE][%s] no amocrm; skip", ptype.value)
            return
        result = await reporter.build(ptype)
        group = settings.CRM_SALES_REPORT_GROUP_ID
        topic = settings.CRM_SALES_REPORT_TOPIC_ID
        bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
        if not group or not bot_rt:
            logger.warning("[SCHEDULE][%s] group/bot missing; skip", ptype.value)
            return
        kw = {"message_thread_id": topic} if topic else {}
        await bot_rt.send_message(group, result.telegram_text, **kw)
        logger.info("[SCHEDULE][%s] CRM report sent to %s", ptype.value, group)
    except Exception as exc:
        logger.error("[SCHEDULE][%s] Error: %s", ptype.value, exc)


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

    if _is_due(now, 19, 30):
        await _send_period_report(PeriodType.DAILY, now, task)


async def _check_weekly_and_stagnation(now: datetime, task: Any) -> None:
    today_str = now.strftime("%Y-%m-%d")
    if now.weekday() == 0 and _is_due(now, 9, 0):
        await _send_period_report(PeriodType.WEEKLY, now, task)

    if now.day == 1 and _is_due(now, 9, 0):
        await _send_period_report(PeriodType.MONTHLY, now, task)

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
