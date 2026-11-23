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
from src.services.core.crm.daily_report.models import PeriodType, previous_anchor

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
        if ptype is PeriodType.DAILY:
            result = await reporter.build(ptype)
        else:
            result = await reporter.build(ptype, previous_anchor(ptype, now.date()))
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


async def _send_daily_summary(now, task, *, reporter_factory=None):
    """amoBot uslubidagi kunlik hisobot, o'zbek tilida."""
    if _is_job_sent(task, f"crm_daily_summary_{now:%Y-%m-%d}"):
        return
    try:
        reporter = (reporter_factory or _default_period_reporter)()
        if reporter is None:
            logger.warning("[SCHEDULE][SUMMARY] no amocrm; skip")
            return
        today = now.date()
        stats = await reporter.fetch_weekly_stats(today, today)
        group = settings.CRM_SALES_REPORT_GROUP_ID
        topic = settings.CRM_SALES_REPORT_TOPIC_ID
        bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
        if not group or not bot_rt:
            logger.warning("[SCHEDULE][SUMMARY] group/bot missing; skip")
            return
        kw = {"parse_mode": "html", "disable_web_page_preview": True}
        if topic:
            kw["message_thread_id"] = topic
        await bot_rt.send_message(group, reporter.format_daily_summary_uz(stats), **kw)
        logger.info("[SCHEDULE][SUMMARY] daily summary sent to %s", group)
    except Exception as exc:
        logger.error("[SCHEDULE][SUMMARY] Error: %s", exc)


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
        if not _is_job_sent(task, job_key):
            from src.schedulers.bg_monitor.helpers import (
                _env_enabled,
                check_system_status_alert,
            )

            alert = await check_system_status_alert(
                include_ok=_env_enabled("STATUS_NOTIFY_OK", default=False)
            )
            if alert:
                bot_client = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                owner_id = getattr(settings, "OWNER_ID", None)
                sent = False
                if bot_client and owner_id:
                    try:
                        from src.services.core.telegram.telegram_ai_features import (
                            get_owner_topic_id,
                        )

                        topic_id = get_owner_topic_id("system")
                        kw = {
                            "parse_mode": "HTML",
                            **({"message_thread_id": topic_id} if topic_id else {}),
                        }
                        await bot_client.send_message(owner_id, alert, **kw)
                        sent = True
                    except Exception as exc:
                        logger.error("[SCHEDULE][STATUS] Error: %s", exc)
                if not sent and getattr(m, "client", None):
                    try:
                        await m.notify_admin(alert, m.client, parse_mode="html")
                    except Exception as exc:
                        logger.error("[SCHEDULE][STATUS] Fallback error: %s", exc)


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

    if _is_due(now, 19, 0):
        await _send_daily_summary(now, task)
    # 19:00 window check: pull & relay amobot daily report if missed by real-time event
    if now.hour == 19 and now.minute in (0, 5, 10, 15) and not _is_job_sent(task, f"amobot_daily_report_{today_str}"):
        try:
            from src.services.core.crm.amobot_daily_report import check_and_relay_amobot_report
            bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
            client = getattr(m, "client", None)
            db = getattr(getattr(m, "msg_controller", None), "db", None)
            if client and bot_rt:
                handled = await check_and_relay_amobot_report(client, bot_rt, db)
                if handled:
                    _is_job_sent(task, f"amobot_daily_report_{today_str}")
                    logger.info("[SCHEDULE] amobot daily report polled and relayed.")
        except Exception as exc:
            logger.error("[SCHEDULE][AMOBOT_REPORT] Error: %s", exc)

    # 19:05: har bir sotuvchiga kunlik qoʻngʻiroqlar hisoboti (Rich/Widget) oʻz topicʻiga
    if _is_due(now, 19, 5) and now.weekday() != 6 and not _is_job_sent(task, f"seller_daily_calls_{today_str}"):
        try:
            from src.schedulers.seller_daily_calls_report import is_enabled, send_seller_daily_call_reports
            if is_enabled():
                await send_seller_daily_call_reports(now)
        except Exception as exc:
            logger.error("[SCHEDULE][SELLER_CALLS] Error: %s", exc)

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
