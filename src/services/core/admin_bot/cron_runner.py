import os
import io
import time
import json
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.services.core.crm.crm_night_shift import CRMNightShift
from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)
from src.services.core.business_command_center import (
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()

class AdminCronRunnerMixin:
    async def run_scheduler(self):
        """Fon rejimida vaqtni nazorat qilish va vazifalarni ishga tushirish.

        JADVAL:
        - 09:45 — Morning Briefing (Qarorlar uchun ma'lumot)
        - 10:00 — Daily Mission Distribution (Plan)
        - 13:00 — Lunch Reminder (Ertalabki vazifalar eslatmasi)
        - 14:00 — Afternoon Mission Distribution (Plan)
        - 01:00 — Night Shift (CRM tozalash)
        - 02:00 — Intelligence Audit (Kechalik AI tahlil)
        - 21:00 — Evening Fact Report (Plan vs Natija, hisobot talab qilish)
        """
        import src.api_server as api_server_module

        logger.info("👸 [ADMIN_BOT] Full Autonomous Scheduler v2.0 ishga tushdi! 🛡️")
        while True:
            try:
                now = get_local_now()
                current_time = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")

                if is_quiet_hours(now):
                    logger.debug(
                        "[SCHEDULER] Quiet hours active. Automatic Telegram jobs are paused."
                    )
                    await asyncio.sleep(30)
                    continue

                # 1. Morning Briefing (09:45)
                if current_time == "09:45":
                    job_id = f"morning_briefing_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Morning Briefing boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                send_morning_briefing,
                            )

                            await send_morning_briefing()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "☀️ Morning Briefing",
                                "Kunlik brifing jamoaga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[BRIEFING ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Morning Briefing", f"Xatolik: {e}", "error"
                            )

                # 1.5 Daily Plan Discipline (10:15, 13:00, 16:30)
                daily_plan_slots = {
                    "10:15": "initial",
                    "13:00": "reminder",
                    "16:30": "escalation",
                }
                if current_time in daily_plan_slots:
                    phase = daily_plan_slots[current_time]
                    job_id = f"daily_plan_{phase}_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            f"[SCHEDULER] Daily plan discipline phase={phase}..."
                        )
                        try:
                            from src.services.core.proactive_worker import (
                                demand_daily_plans,
                            )

                            sent = await demand_daily_plans(phase)
                            await self.db.set_state(job_id, "done")
                            if sent:
                                api_server_module.add_activity(
                                    "ðŸ“ Daily Plan Discipline",
                                    f"Kunlik plan bo'yicha {phase} faza yuborildi.",
                                    "success",
                                )
                        except Exception as e:
                            logger.error(f"[DAILY PLAN ERROR] {e}")
                            api_server_module.add_activity(
                                "âš ï¸ Daily Plan Error", str(e), "error"
                            )

                # 2. Daily Missions (10:00 va 14:00)
                if current_time in ["10:00", "14:00"]:
                    job_id = f"daily_{today}_{current_time}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            f"👸 [SCHEDULER] Mission Distribution {current_time}..."
                        )
                        try:
                            await self.trigger_daily_missions()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                f"🎯 Mission Control ({current_time})",
                                "Lidlar menejerlarga taqsimlandi va 'Morning Plan' guruhga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[MISSION ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Mission Error", str(e), "error"
                            )

                # 2.25 Client Journey Excellence (11:00 va 17:00)
                if current_time in ["11:00", "17:00"]:
                    job_id = f"client_journey_{today}_{current_time}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            "[SCHEDULER] Client Journey Excellence boshlandi..."
                        )
                        try:
                            from src.services.core.proactive_worker import (
                                check_client_journey_excellence,
                            )

                            sent = await check_client_journey_excellence()
                            await self.db.set_state(job_id, "done")
                            if sent:
                                api_server_module.add_activity(
                                    "ðŸŒŸ Client Journey",
                                    "Mijoz yo'li bo'yicha wow-service mikromanagement report yuborildi.",
                                    "success",
                                )
                        except Exception as e:
                            logger.error(f"[CLIENT JOURNEY ERROR] {e}")
                            api_server_module.add_activity(
                                "âš ï¸ Client Journey Error", str(e), "error"
                            )

                # 2.5 Lunch Reminder (13:00) - Ertalabki vazifalar haqida eslatish
                if current_time == "13:00":
                    job_id = f"lunch_reminder_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Lunch Reminder boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                send_lunch_reminder,
                            )

                            await send_lunch_reminder()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "🍽 Lunch Reminder",
                                "Tushlik vaqtida ertalabki vazifalar haqida eslatma yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[LUNCH ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Lunch Reminder Error", str(e), "error"
                            )

                # 3. Evening Fact Report (21:00)
                if current_time == "21:00":
                    job_id = f"evening_fact_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Evening Fact Report boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                send_evening_fact_report,
                            )

                            await send_evening_fact_report()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "📊 Plan-Fakt Tahlili",
                                "Kechki natijalar auditlandi va Telegram guruhiga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[FACT REPORT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Fact Report Error", str(e), "error"
                            )

                # 4. Night Shift — CRM Cleanup (01:00)
                if current_time == "01:00":
                    job_id = f"night_shift_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            "👸 [SCHEDULER] Night Shift CRM Cleanup boshlandi..."
                        )
                        api_server_module.add_activity(
                            "🧹 Night Shift",
                            "AmoCRM dublikatlar va qotib qolgan lidlar tozalanmoqda...",
                            "thinking",
                        )
                        try:
                            if self.night_shift:
                                await self.night_shift.run_cleanup()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "✅ Night Shift",
                                "CRM muvaffaqiyatli tozalandi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[NIGHT SHIFT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Night Shift Error", str(e), "error"
                            )

                # 5. Intelligence Audit — Tungi AI Tahlili (02:00)
                if current_time == "02:00":
                    job_id = f"intelligence_audit_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in (
                        "done",
                        "running",
                    ):  # Check both done and running states
                        # Set state immediately to prevent duplicate runs from scheduler
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            "👸 [SCHEDULER] Intelligence Audit boshlandi (tungi)..."
                        )
                        api_server_module.add_activity(
                            "🕵️ Intelligence Audit",
                            "Tungi AI tahlili boshlandi. Faollik loglari o'rganilmoqda...",
                            "thinking",
                        )
                        try:
                            from src.services.core.audit_agent import AuditAgent
                            import src.config as config

                            _audit = AuditAgent(
                                api_key=config.GEMINI_API_KEY, db=self.db
                            )
                            report = await _audit.generate_audit_report(limit=200)
                            # Egaga yuborish (user_client orqali)
                            from src.api_server import user_client as uc

                            if uc:
                                # [FIX: PeerUser] Use 'me' directly for safer delivery to self
                                try:
                                    logger.info(
                                        "📨 [AUDIT] Sending nighttime report to 'me'..."
                                    )
                                    await uc.send_message(
                                        "me",
                                        f"🦉 **OISHA: Tungi Intelligence Audit**\n\n{report}",
                                    )
                                except Exception as entity_error:
                                    logger.error(f"[AUDIT PEER ERROR] {entity_error}")
                                    # Fallback: try direct 'me'
                                    await uc.send_message(
                                        "me",
                                        f"🦉 **OISHA: Tungi Intelligence Audit**\n\n{report}",
                                    )
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "✅ Intelligence Audit",
                                "Tungi audit yakunlandi. Hisobot Telegramga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[AUDIT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Audit Error", str(e), "error"
                            )

                # 5.5 Junk Audit — CRM Hygiene (02:30)
                if current_time == "02:30":
                    job_id = f"junk_audit_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Junk Leads Audit boshlandi...")
                        api_server_module.add_activity(
                            "🧹 Junk Audit",
                            "CRM bekorchi sdelkalar tahlili boshlandi...",
                            "thinking",
                        )
                        try:
                            from src.services.core.proactive_worker import (
                                send_junk_leads_report,
                            )

                            await send_junk_leads_report()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "✅ Junk Audit",
                                "Bekorchi sdelkalar tahlili yakunlandi va guruhga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[JUNK AUDIT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Junk Audit Error", str(e), "error"
                            )

                # 6. Menejer Scorecard (18:30) — Kunlik KPI
                if current_time == "18:30":
                    job_id = f"scorecard_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("📊 [SCHEDULER] Menejer Scorecard boshlandi...")
                        try:
                            from src.services.core.sales_analytics import SalesAnalytics
                            from telegram import Bot
                            import src.config as config

                            bot_token = getattr(config, "BOT_TOKEN", None)
                            group_id = getattr(config, "CRM_GROUP_ID", None)
                            thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
                            if bot_token and group_id:
                                tg_bot = Bot(token=bot_token)
                                analytics = SalesAnalytics(bot=tg_bot)
                                await analytics.send_scorecard(group_id, thread_id)
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "📊 Scorecard",
                                "Menejer KPI hisoboti yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[SCORECARD ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Scorecard Error", str(e), "error"
                            )

                # 7. Stagnatsiya Alert (12:00) — Harakatsiz lidlar
                if current_time == "12:00":
                    job_id = f"stagnation_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("[SCHEDULER] Sales Conversion Push boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                check_amocrm_stagnation,
                            )

                            await check_amocrm_stagnation()
                            # Stagnation Alert is part of same job
                            from src.services.core.sales_analytics import SalesAnalytics
                            from telegram import Bot

                            bot_token = getattr(config, "BOT_TOKEN", None)
                            group_id = getattr(config, "CRM_GROUP_ID", None)
                            thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
                            if bot_token and group_id:
                                tg_bot = Bot(token=bot_token)
                                analytics = SalesAnalytics(bot=tg_bot)
                                await analytics.send_stagnation_alert(
                                    group_id, thread_id
                                )
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "🚀 Sales Conversion Push",
                                "Harakatsiz lidlar bo'yicha conversion push yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[STAGNATION ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Stagnation Error", str(e), "error"
                            )

                # 9. Juma Mubarak (Juma 09:00) — Outreach
                if now.weekday() == 4 and current_time == "09:00":
                    job_id = f"juma_mubarak_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        logger.info("🕌 [SCHEDULER] Juma Mubarak outreach boshlandi...")
                        try:
                            if self.juma_notifier:
                                await self.juma_notifier.check_and_send()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "🕌 Juma Mubarak",
                                "Kursdoshlarga tabriklar yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[JUMA ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Juma Error", str(e), "error"
                            )

                # 8. Pipeline Funnel (Dushanba 09:30) — Haftalik conversiya
                if now.weekday() == 0 and current_time == "09:30":
                    job_id = f"funnel_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("📊 [SCHEDULER] Pipeline Funnel boshlandi...")
                        try:
                            from src.services.core.sales_analytics import SalesAnalytics
                            from telegram import Bot
                            import src.config as config

                            bot_token = getattr(config, "BOT_TOKEN", None)
                            group_id = getattr(config, "CRM_GROUP_ID", None)
                            thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
                            if bot_token and group_id:
                                tg_bot = Bot(token=bot_token)
                                analytics = SalesAnalytics(bot=tg_bot)
                                await analytics.send_funnel_report(group_id, thread_id)
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "📊 Pipeline Funnel",
                                "Haftalik conversiya tahlili yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[FUNNEL ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Funnel Error", str(e), "error"
                            )

                # Har 30 soniyada tekshirish
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"[SCHEDULER ERROR] {e}")
                await asyncio.sleep(60)
