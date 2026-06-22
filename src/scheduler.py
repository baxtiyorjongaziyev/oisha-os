"""
Oisha-OS background scheduler.

Extracted from src/main.py to reduce the God Object. Owns the single
5-minute monitoring loop (`background_monitor_task`) that drives all
time-based jobs: stagnation checks, lead reengagement, daily/weekly
reports, Juma greetings, mission distribution and the keep-alive pulse.

Runtime state (client, msg_controller, juma_notifier, notify_admin,
TN5_GROUP_ID) lives on the `src.main` module — boot.py assigns it there
during startup. This module reads it via the `m.` alias so there is a
single source of truth and no duplicated wiring.
"""
from __future__ import annotations

import asyncio
import os
import logging

from src.settings import settings
from telethon import functions
from src.controllers.surgical_integration import get_surgical_integration
import src.main as m

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("[SCHEDULE] Invalid %s=%r; using default %d", name, raw, default)
        return default


def _is_due(now, hour: int, minute: int, window_min: int = 5) -> bool:
    """True if now is within [minute, minute+window_min) of the given hour."""
    if now.hour != hour:
        return False
    return minute <= now.minute < (minute + window_min)


async def background_monitor_task() -> None:
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish (AmoCRM + Airtable).

    Runs indefinitely with 5-minute intervals between checks.
    Handles errors gracefully and continues operation.
    """
    from src.services.core.proactive_worker import (
        check_amocrm_stagnation,
        check_airtable_deadlines,
        send_overdue_nudges,
        check_airtable_stagnation,
        check_client_journey_excellence,
    )
    from src.services.core.leads.lead_operating_system import LeadOperatingSystem
    from src.time_utils import get_local_now, is_quiet_hours

    logger.info("[MONITOR] Boshlandi (Interval: 5 daqiqa)")

    while True:
        try:
            now = get_local_now()

            if is_quiet_hours(now):
                logger.debug(
                    "[MONITOR] Quiet hours active. Automatic notifications are paused."
                )
                await asyncio.sleep(300)
                continue

            # 1. Stagnatsiya va Deadline tekshirish
            await check_amocrm_stagnation()
            await check_airtable_stagnation()
            await check_client_journey_excellence()
            await check_airtable_deadlines()

            if m.msg_controller:
                if not hasattr(background_monitor_task, "_lead_os"):
                    background_monitor_task._lead_os = LeadOperatingSystem(
                        m.msg_controller, m.msg_controller.db
                    )
                last_cycle_at = getattr(background_monitor_task, "_lead_cycle_at", None)
                if not last_cycle_at or (now - last_cycle_at).total_seconds() >= 900:
                    await background_monitor_task._lead_os.review_recent_active_leads(
                        limit=12,
                        lookback_hours=72,
                        execute_actions=True,
                    )
                    background_monitor_task._lead_cycle_at = now

                if any(_is_due(now, h, 0) for h in [10, 14, 18, 22]):
                    today_str = now.strftime("%Y-%m-%d")
                    job_key = f"lead_reengagement_{now.hour}_{today_str}"
                    if not hasattr(background_monitor_task, "_sent_jobs"):
                        background_monitor_task._sent_jobs = set()
                    if job_key not in background_monitor_task._sent_jobs:
                        await background_monitor_task._lead_os.run_reengagement_cycle(
                            limit=8
                        )
                        background_monitor_task._sent_jobs.add(job_key)

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
                                if fin_group and m.client:
                                    try:
                                        await m.client.send_message(
                                            fin_group,
                                            report_html,
                                            parse_mode="html",
                                            reply_to=pnl_topic,
                                        )
                                        delivered = True
                                    except Exception as send_exc:
                                        logger.error(
                                            "[SCHEDULE][REPORT] Finance group delivery failed: %s",
                                            send_exc,
                                        )
                                if not delivered and m.client:
                                    # Fallback to owner DM (HTML so tags render correctly)
                                    await m.client.send_message(
                                        "me", report_html, parse_mode="html"
                                    )
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
                            if m.TN5_GROUP_ID and m.client:
                                send_kwargs = {}
                                if settings.TOPIC_REPORTS_ID:
                                    send_kwargs["reply_to"] = settings.TOPIC_REPORTS_ID
                                await m.client.send_message(
                                    m.TN5_GROUP_ID,
                                    report_text,
                                    **send_kwargs,
                                )
                                logger.info(f"[SCHEDULE] CRM Daily reportagram sent to group {m.TN5_GROUP_ID}.")
                            elif m.client:
                                await m.notify_admin(report_text, m.client)
                    except Exception as rep_exc:
                        logger.error(f"[SCHEDULE][CRM_REPORT] Error: {rep_exc}")
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

                            if m.TN5_GROUP_ID and m.client:
                                await m.client.send_message(
                                    m.TN5_GROUP_ID,
                                    report_text,
                                    **send_kwargs,
                                )
                            elif m.client:
                                await m.notify_admin(report_text, m.client)

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

            if any(_is_due(now, h, 0) for h in [10, 22]):
                today_str = now.strftime("%Y-%m-%d")
                job_key = f"stagnation_alert_{now.hour}_{today_str}"
                if not hasattr(background_monitor_task, "_sent_jobs"):
                    background_monitor_task._sent_jobs = set()
                if job_key not in background_monitor_task._sent_jobs:
                    try:
                        if m.msg_controller:
                            alert = (
                                await m.msg_controller.enterprise_reporter.get_stagnant_leads_alert()
                            )
                            if alert:
                                target_group = settings.STAGNATION_GROUP_ID
                                target_topic = settings.STAGNATION_TOPIC_ID
                                if target_group and m.client:
                                    await m.client.send_message(
                                        target_group,
                                        alert,
                                        reply_to=target_topic,
                                    )
                                    logger.info(
                                        f"[SCHEDULE] Stagnation alert sent to group {target_group}, topic {target_topic} at {now.hour}:00"
                                    )
                                elif m.client:
                                    await m.notify_admin(alert, m.client)
                                    logger.info(
                                        f"[SCHEDULE] Stagnation alert sent to admin at {now.hour}:00"
                                    )
                    except Exception as stag_exc:
                        logger.error(f"[SCHEDULE][STAGNATION] Error: {stag_exc}")
                    background_monitor_task._sent_jobs.add(job_key)

            # 5. [ALWAYS ONLINE] Keep-alive pulse
            if m.client:
                try:
                    await m.client(functions.account.UpdateStatusRequest(offline=False))
                    logger.debug("[HEARTBEAT] Account status set to ONLINE")
                except Exception as e:
                    logger.warning(f"[HEARTBEAT] Failed to update status: {e}")

            # Intervalni 5 daqiqaga tushirdik (300 soniya)
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")
            await asyncio.sleep(60)
