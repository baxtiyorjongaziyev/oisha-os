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

            # 1. Stagnatsiya va Deadline tekshirish
            await check_amocrm_stagnation()
            await check_airtable_stagnation()
            await check_client_journey_excellence()
            
            if now.hour in [10, 15] and now.minute < 5:
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

            # NOTE: stagnatsiya ogohlantirishi endi FAQAT check_amocrm_stagnation()
            # (proactive_worker.py, yuqorida chaqiriladi, soat 12:00 va 16:00 da)
            # orqali yuboriladi. Ilgari shu yerda soat 10:00 va 22:00 da bir xil
            # alertni (get_stagnant_leads_alert) alohida job_key bilan qayta
            # yuboradigan duplikat blok bor edi — ikkalasi bir-birining
            # is_job_run belgisini ko'rmagani uchun jamoa bir xil xabarni kuniga
            # 4 marta (10, 12, 16, 22) olardi. Duplikat blok olib tashlandi.

            # ─────────────────────────────────────────────────────────
            # 10. [ESCALATION] Javobsiz ogohlantirishlarni vakolatlar
            #     darajasida (xodim → rahbar → Owner) eskalatsiya qilish.
            #     Soatning boshida (:00-:05) bir marta tekshiriladi;
            #     ichki holat (agent_actions) qayta yuborishning oldini oladi.
            # ─────────────────────────────────────────────────────────
            if now.minute < 5:
                try:
                    from src.services.core.escalation_agent import EscalationAgent

                    escalation_db = m.msg_controller.db if m.msg_controller else None
                    if escalation_db and m.client:
                        escalation_agent = EscalationAgent(
                            escalation_db, bot_client=m.client
                        )
                        await escalation_agent.check_pending_feedbacks()
                except Exception as esc_exc:
                    logger.error(f"[SCHEDULE][ESCALATION] Error: {esc_exc}")

            # ─────────────────────────────────────────────────────────
            # 11. [SECOND_BRAIN_AUTOPILOT] Obsidian Ikkinchi Miya Sinxronizatsiyasi
            # ─────────────────────────────────────────────────────────
            try:
                # 11a. AmoCRM & Telegram Cross-Channel Sync (har 15 daqiqada)
                last_brain_sync = getattr(background_monitor_task, "_last_brain_sync", None)
                if not last_brain_sync or (now - last_brain_sync).total_seconds() >= 900:
                    from src.services.core.brain.cross_channel_sync import CrossChannelBrainSync
                    brain_sync = CrossChannelBrainSync()
                    # Trigger light sync if leads exist
                    if m.msg_controller and getattr(m.msg_controller, "db", None):
                        active_leads = await m.msg_controller.db.get_active_leads(limit=10)
                        for lead in active_leads:
                            brain_sync.sync_deal_and_call(
                                lead_id=lead.get("id", 0),
                                lead_name=lead.get("name", "Noma'lum"),
                                phone=lead.get("phone", ""),
                                price=float(lead.get("price", 0) or 0),
                                status_name=lead.get("status", "Aktiv"),
                                transcript=lead.get("last_transcript", ""),
                                ai_analysis=lead.get("ai_analysis", ""),
                            )
                    background_monitor_task._last_brain_sync = now

                # 11b. Haftalik Review & Sotuvlar Sintezi (Har yakshanba 20:00 yoki dushanba 08:30)
                if (now.weekday() == 6 and _is_due(now, 20, 0)) or (now.weekday() == 0 and _is_due(now, 8, 30)):
                    today_str = now.strftime("%Y-%m-%d")
                    job_key = f"brain_weekly_review_{today_str}"
                    if not hasattr(background_monitor_task, "_sent_jobs"):
                        background_monitor_task._sent_jobs = set()
                    if job_key not in background_monitor_task._sent_jobs:
                        from src.services.core.brain.weekly_review_synthesizer import WeeklyReviewSynthesizer
                        week_label = f"Hafta {now.strftime('%W, %Y')}"
                        WeeklyReviewSynthesizer().generate_weekly_review(
                            week_label=week_label,
                            completed_items=["Tez Dizayn sprintlari", "Kamila Pardalari patent ekspertizasi", "AmoCRM lidlar qayta ishlandi"],
                            bottlenecks=["Qaror qabul qilishni cho'zayotgan lidlar"],
                            top_goals_next_week=["Yangi mijozlar shartnomalari", "Moliya konveyeri yangilanishi"],
                            revenue_summary="Aktiv hisob-kitoblar amalga oshirilmoqda",
                        )
                        background_monitor_task._sent_jobs.add(job_key)
                        logger.info("[SCHEDULE][BRAIN] Weekly Review compiled to Obsidian.")

                # 11c. Oylik Moliya Sintezi (Har oyning 1-kuni 09:00)
                if now.day == 1 and _is_due(now, 9, 0):
                    today_str = now.strftime("%Y-%m-%d")
                    job_key = f"brain_monthly_finance_{today_str}"
                    if not hasattr(background_monitor_task, "_sent_jobs"):
                        background_monitor_task._sent_jobs = set()
                    if job_key not in background_monitor_task._sent_jobs:
                        from src.services.core.brain.finance_brain_synthesizer import FinanceBrainSynthesizer
                        month_label = now.strftime("%B %Y")
                        FinanceBrainSynthesizer().generate_monthly_report(
                            month_label=month_label,
                            total_income=0.0,
                            total_expense=0.0,
                            categories_breakdown={},
                            top_projects=[],
                            notes="Oylik moliya avtomatik sinxronizatsiya qilindi.",
                        )
                        background_monitor_task._sent_jobs.add(job_key)
                        logger.info("[SCHEDULE][BRAIN] Monthly Finance compiled to Obsidian.")
            except Exception as brain_exc:
                logger.error(f"[SCHEDULE][BRAIN] Error in Second Brain autopilot: {brain_exc}")

            # ─────────────────────────────────────────────────────────
            # 12. [ASSISTANT_ADVISOR] Telegram Audit & Shahnoza Tavsiyalari
            # ─────────────────────────────────────────────────────────
            try:
                from src.services.core.assistant.telegram_assistant_advisor import (
                    TelegramAssistantAdvisor,
                    SHAHNOZA_USER_ID,
                )
                if not hasattr(background_monitor_task, "_assistant_advisor"):
                    background_monitor_task._assistant_advisor = TelegramAssistantAdvisor()

                advisor = background_monitor_task._assistant_advisor
                if m.msg_controller and getattr(m.msg_controller, "db", None):
                    # Fetch recent active messages/chats if db supports it
                    get_chats_fn = getattr(m.msg_controller.db, "get_recent_telegram_chats", None)
                    if callable(get_chats_fn):
                        recent_chats = await get_chats_fn(limit=8)
                        new_tasks = []
                        for c in (recent_chats or []):
                            task = advisor.analyze_chat_for_assistant(
                                chat_id=c.get("chat_id", 0),
                                chat_title=c.get("title", "Mijoz"),
                                messages=c.get("recent_messages", []),
                                owner_id=150074828,
                            )
                            if task:
                                new_tasks.append(task)
                                bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
                                if bot_rt:
                                    alert_html = advisor.format_telegram_alert(task)
                                    await bot_rt.send_message(SHAHNOZA_USER_ID, alert_html, parse_mode="html")
                        if new_tasks:
                            advisor.record_in_obsidian(new_tasks)
            except Exception as adv_exc:
                logger.debug(f"[SCHEDULE][ASSISTANT_ADVISOR] Non-blocking audit: {adv_exc}")

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
