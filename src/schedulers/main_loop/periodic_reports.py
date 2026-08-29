"""
Daily and weekly scheduled reporting jobs (CRM report, hisobchi roast, stagnation).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from src.settings import settings
import src.main as m
from src.schedulers.main_loop.helpers import _is_due

logger = logging.getLogger("OishaScheduler")


async def run_periodic_reports(now: datetime, background_monitor_task: Any) -> None:
    # 3. Muddati o'tgan eslatmalar (17:00 - faqat bir marta)
    if _is_due(now, 17, 0):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"overdue_nudges_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs:
            await send_overdue_nudges()
            background_monitor_task._sent_jobs.add(job_key)

    # 4. Har 4 soatda "Hushyor" xabari (13:00, 17:00, 21:00 - faqat bir marta)
    if any(_is_due(now, h, 0) for h in [13, 17, 21]):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"status_notify_{now.hour}_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs and m.client:
            await m.notify_admin(
                "👸 **Oisha OS: Tizim nazoratda**\nAmoCRM, Airtable va Lead-Scraper barqaror ishlamoqda.",
                m.client,
            )
            background_monitor_task._sent_jobs.add(job_key)

    # ─────────────────────────────────────────────────────────
    # 6. [JUMA] Juma kuni 09:00 — JumaNotifier
    # ─────────────────────────────────────────────────────────
    if now.weekday() == 4 and _is_due(now, 9, 0):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"juma_notifier_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs:
            try:
                if m.juma_notifier:
                    await m.juma_notifier.check_and_send()
                    logger.info("[SCHEDULE] JumaNotifier sent.")
                else:
                    logger.warning(
                        "[SCHEDULE] JumaNotifier not initialized, skipping."
                    )
            except Exception as juma_exc:
                logger.error(f"[SCHEDULE][JUMA] Error: {juma_exc}")
            background_monitor_task._sent_jobs.add(job_key)

    # ─────────────────────────────────────────────────────────
    # 7. [MISSIONS] Har kuni 09:30 — MissionControl (Surgical Missions)
    # ─────────────────────────────────────────────────────────
    if _is_due(now, 9, 30):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"surgical_missions_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs:
            try:
                from src.services.core.mission_control import MissionControl

                mc = MissionControl(
                    db=m.msg_controller.db if m.msg_controller else None
                )
                managers = await mc.get_manager_list()
                if managers:
                    await mc.distribute_missions(managers)
                    logger.info(
                        f"[SCHEDULE] Surgical Missions distributed to {len(managers)} managers."
                    )
                else:
                    logger.warning(
                        "[SCHEDULE] No managers found for mission distribution."
                    )
            except Exception as mc_exc:
                logger.error(f"[SCHEDULE][MISSIONS] Error: {mc_exc}")
            background_monitor_task._sent_jobs.add(job_key)

    # ─────────────────────────────────────────────────────────
    # 8. [REPORT] Har kuni 18:00 — EnterpriseReporter kunlik hisobot
    # ─────────────────────────────────────────────────────────
    if _is_due(now, 18, 0):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"daily_report_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs:
            try:
                if m.msg_controller:
                    report = (
                        await m.msg_controller.enterprise_reporter.get_daily_efficiency_report()
                    )
                    if report:
                        # Report body is HTML-formatted (<b>…</b>), so all
                        # delivery paths must use parse_mode="html".
                        fin_group = settings.HISOBCHI_FINANCE_GROUP_ID
                        pnl_topic = settings.HISOBCHI_PNL_TOPIC_ID
                        report_html = f"📊 <b>KUNLIK HISOBOT</b>\n\n{report}"
                        delivered = False
                        bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                        if fin_group:
                            if bot_rt:
                                try:
                                    bot_kwargs = {"parse_mode": "html"}
                                    if pnl_topic:
                                        bot_kwargs["message_thread_id"] = pnl_topic
                                    await bot_rt.send_message(fin_group, report_html, **bot_kwargs)
                                    delivered = True
                                except Exception as send_exc:
                                    logger.warning("[SCHEDULE][REPORT] Bot runtime send failed: %s", send_exc)
                            if not delivered and bot_rt and getattr(settings, "OWNER_ID", None):
                                await bot_rt.send_message(settings.OWNER_ID, report_html, parse_mode="html")
                        logger.info("[SCHEDULE] Daily EnterpriseReport sent.")
            except Exception as rep_exc:
                logger.error(f"[SCHEDULE][REPORT] Error: {rep_exc}")
            background_monitor_task._sent_jobs.add(job_key)

    # ─────────────────────────────────────────────────────────
    # 8b. [CRMDailyReport] Har kuni 19:30 — AmoCRM Kunlik Hisobot (Reportagram)
    # ─────────────────────────────────────────────────────────
    if _is_due(now, 19, 30):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"crm_daily_report_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs:
            try:
                from src.services.core.crm.crm_daily_report import CRMDailyReporter
                amocrm_client = None
                if m.msg_controller and getattr(m.msg_controller, "crm", None):
                    amocrm_client = getattr(m.msg_controller.crm, "amocrm", None)
                if not amocrm_client:
                    amocrm_client = get_surgical_integration().amocrm
                
                if amocrm_client:
                    reporter = CRMDailyReporter(amocrm=amocrm_client)
                    stats = await reporter.fetch_stats()
                    prev = reporter._load_prev_stats()
                    report_text = reporter.format_report(stats, prev)
                    
                    # Send to m.TN5_GROUP_ID (or configured CRM_GROUP_ID)
                    target_group = m.TN5_GROUP_ID or getattr(settings, "CRM_GROUP_ID", None)
                    delivered = False
                    bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                    if target_group:
                        if bot_rt:
                            try:
                                send_kwargs = {}
                                if settings.TOPIC_REPORTS_ID:
                                    send_kwargs["message_thread_id"] = settings.TOPIC_REPORTS_ID
                                await bot_rt.send_message(target_group, report_text, **send_kwargs)
                                delivered = True
                                logger.info(f"[SCHEDULE] CRM Daily reportagram sent via bot to {target_group}.")
                            except Exception as b_exc:
                                logger.warning("[SCHEDULE][CRM_REPORT] bot_rt send failed: %s", b_exc)
                        if not delivered and bot_rt and getattr(settings, "OWNER_ID", None):
                            await bot_rt.send_message(settings.OWNER_ID, report_text)
                    elif bot_rt and getattr(settings, "OWNER_ID", None):
                        await bot_rt.send_message(settings.OWNER_ID, report_text)
            except Exception as rep_exc:
                logger.error(f"[SCHEDULE][CRM_REPORT] Error: {rep_exc}")
            background_monitor_task._sent_jobs.add(job_key)

    # ─────────────────────────────────────────────────────────
    # 8d. [AUTO-BRIEFING] Har kuni 09:00 — ROI + KPI + Deadline
    #     Panel tugmalarini avtomatik push qiladi (tugmasiz).
    # ─────────────────────────────────────────────────────────
    if _is_due(now, 9, 0):
        today_str = now.strftime("%Y-%m-%d")
        job_key = f"auto_briefing_{today_str}"
        if not hasattr(background_monitor_task, "_sent_jobs"):
            background_monitor_task._sent_jobs = set()
        if job_key not in background_monitor_task._sent_jobs:
            try:
                if getattr(m, "admin_bot", None):
                    await m.admin_bot.run_auto_briefing()
                    logger.info("[SCHEDULE] Auto-briefing (ROI+KPI+Deadline) yuborildi.")
                else:
                    logger.warning("[SCHEDULE] admin_bot yo'q — brifing o'tkazildi.")
            except Exception as brief_exc:
                logger.error(f"[SCHEDULE][AUTO-BRIEFING] Error: {brief_exc}")
            background_monitor_task._sent_jobs.add(job_key)

    # ─────────────────────────────────────────────────────────
    # 9. [STAGNATION] Har kuni 10:00 va 22:00 — Stagnation Alert
    # ─────────────────────────────────────────────────────────
    # 8c. [CRMWeeklyReport] Har dushanba 09:00 - AmoCRM haftalik hisobot
    weekly_enabled = os.getenv("CRM_WEEKLY_REPORT_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    weekly_weekday = _env_int("CRM_WEEKLY_REPORT_WEEKDAY", 0)
    weekly_hour = _env_int("CRM_WEEKLY_REPORT_HOUR", 9)
    weekly_minute = _env_int("CRM_WEEKLY_REPORT_MINUTE", 0)
    if not 0 <= weekly_weekday <= 6:
        logger.warning("[SCHEDULE] Invalid CRM_WEEKLY_REPORT_WEEKDAY=%s; using 0", weekly_weekday)
        weekly_weekday = 0
    if not 0 <= weekly_hour <= 23:
        logger.warning("[SCHEDULE] Invalid CRM_WEEKLY_REPORT_HOUR=%s; using 9", weekly_hour)
        weekly_hour = 9
    if not 0 <= weekly_minute <= 59:
        logger.warning("[SCHEDULE] Invalid CRM_WEEKLY_REPORT_MINUTE=%s; using 0", weekly_minute)
        weekly_minute = 0
    if (
        weekly_enabled
        and now.weekday() == weekly_weekday
        and _is_due(now, weekly_hour, weekly_minute)
    ):
        try:
            from src.services.core.crm.crm_daily_report import (
                CRMDailyReporter,
                previous_week_range,
            )

            period_start, period_end = previous_week_range(now.date())
            run_key = f"{period_start.isoformat()}_{period_end.isoformat()}"
            job_key = f"crm_weekly_report_{run_key}"

            if not hasattr(background_monitor_task, "_sent_jobs"):
                background_monitor_task._sent_jobs = set()

            already_sent = job_key in background_monitor_task._sent_jobs
            if not already_sent and m.msg_controller and getattr(
                m.msg_controller, "db", None
            ):
                already_sent = await m.msg_controller.db.is_job_run(
                    "crm_weekly_report", run_key
                )

            if not already_sent:
                amocrm_client = None
                if m.msg_controller and getattr(m.msg_controller, "crm", None):
                    amocrm_client = getattr(m.msg_controller.crm, "amocrm", None)
                if not amocrm_client:
                    amocrm_client = get_surgical_integration().amocrm

                if amocrm_client:
                    reporter = CRMDailyReporter(amocrm=amocrm_client)
                    stats = await reporter.fetch_weekly_stats(
                        period_start, period_end
                    )
                    report_text = reporter.format_weekly_report_uz(stats)

                    send_kwargs = {}
                    if settings.TOPIC_REPORTS_ID:
                        send_kwargs["reply_to"] = settings.TOPIC_REPORTS_ID

                    target_group = m.TN5_GROUP_ID or getattr(settings, "CRM_GROUP_ID", None)
                    delivered = False
                    bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                    if target_group:
                        if bot_rt:
                            try:
                                send_kwargs_bot = {}
                                if settings.TOPIC_REPORTS_ID:
                                    send_kwargs_bot["message_thread_id"] = settings.TOPIC_REPORTS_ID
                                await bot_rt.send_message(
                                    target_group,
                                    report_text,
                                    **send_kwargs_bot,
                                )
                                delivered = True
                                logger.info(f"[SCHEDULE] CRM weekly report sent via bot to {target_group}.")
                            except Exception as b_exc:
                                logger.warning("[SCHEDULE][CRM_WEEKLY_REPORT] bot_rt send failed: %s", b_exc)
                        if not delivered and bot_rt and getattr(settings, "OWNER_ID", None):
                            await bot_rt.send_message(settings.OWNER_ID, report_text)
                    elif bot_rt and getattr(settings, "OWNER_ID", None):
                        await bot_rt.send_message(settings.OWNER_ID, report_text)

                    if m.msg_controller and getattr(m.msg_controller, "db", None):
                        await m.msg_controller.db.mark_job_run(
                            "crm_weekly_report", run_key
                        )
                    background_monitor_task._sent_jobs.add(job_key)
                    logger.info(
                        "[SCHEDULE] CRM weekly Uzbek report sent for %s.",
                        run_key,
                    )
                else:
                    logger.warning(
                        "[SCHEDULE][CRM_WEEKLY_REPORT] AmoCRM m.client not ready."
                    )
        except Exception as weekly_exc:
            logger.error(
                f"[SCHEDULE][CRM_WEEKLY_REPORT] Error: {weekly_exc}"
            )

