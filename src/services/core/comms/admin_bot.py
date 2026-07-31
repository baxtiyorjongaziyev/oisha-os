import os
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()


from src.handlers.admin.admin_handlers_mixin import AdminHandlersMixin

class AdminBot(AdminHandlersMixin):
    """Oisha-OS Enterprise Admin Bot (Surgical Logic)."""
    def __init__(
        self,
        bot_client,
        user_client,
        db: Database,
        msg_controller: MessageController,
        access_manager: "AccessManager",
        night_shift: CRMNightShift = None,
        team_group_id: int = None,
        juma_notifier=None,
        bot_runtime: BotRuntimePort = None,
    ):
        self.bot_client = bot_client
        self.bot_runtime = bot_runtime or TelethonBotRuntime(bot_client)
        self.user_client = user_client
        self.db = db
        self.msg_controller = msg_controller
        self.access_manager = access_manager
        self.night_shift = night_shift
        self.team_group_id = team_group_id
        self.juma_notifier = juma_notifier
        self.active_searches = {}  # user_id -> timestamp
        self.pending_drafts = {}  # draft_id -> draft_text
        from src.services.core.self_improvement import SelfImprovementService

        self.self_improvement = SelfImprovementService(
            db,
            bot_client=self.bot_runtime,
            owner_id=access_manager.owner_id,
        )

        # [EXPERT ADVICE] Professional scripts to obtain phone numbers
        self.PHONE_GETTING_SCRIPTS = {
            "agency_standard": (
                "📍 **Agency Standard:**\n"
                '"Tafsilotlar uchun rahmat! Loyihani texnik tomondan baholashimiz uchun '
                "siz bilan telefon orqali bog'lansak bo'ladimi? Raqamingizni qoldirsangiz, "
                'mutaxassisimiz bilan vaqtni kelishib olamiz."'
            ),
            "value_first": (
                "🎁 **Value-First (Kasbiy):**\n"
                "\"Sizning sohangiz bo'yicha bizda tayyor keyslar va narxlar paketi bor. "
                "Ularni Telegram orqali yuborishim uchun kontaktlaringizni yangilab yuborsangiz (ulashsangiz), "
                "sizga mos yechimni jo'nataman.\""
            ),
            "emergency_pm": (
                "⚡ **Dynamic (PM uslubi):**\n"
                "\"Loyiha bo'yicha tezkor savollar bor edi. Yozishib o'tirmasdan, "
                "qisqa qo'ng'iroqda hal qilsak tezroq bitar edi. Qaysi raqamga bog'lansak bo'ladi?\""
            ),
        }

    def _outbound_bot_runtime(self) -> BotRuntimePort:
        runtime = getattr(self, "bot_runtime", None)
        if runtime is not None:
            return runtime
        runtime = TelethonBotRuntime(self.bot_client)
        self.bot_runtime = runtime
        return runtime

    async def start(self):
        """Botni eventlarini ro'yxatdan o'tkazish va schedulerni parallel yuritish."""
        logger.info("[ADMIN_BOT] Oisha Enterprise v2.1 ishga tushmoqda...")

        # [AUDIT: HEARTBEAT] Proof of life (log spam oldini olish: 5 daqiqa, DEBUG)
        async def heartbeat():
            while True:
                logger.debug(
                    "👸 [ADMIN_BOT] HEARTBEAT: Oisha is alive and listening... 🛡️"
                )
                await asyncio.sleep(300)

        # [DISTRIBUTION] Yuklash (Settings ni DB bilan sinxronlash)
        from src.settings import settings

        db_mode = await self.db.get_state("lead_distribution_mode")
        if db_mode:
            settings.LEAD_DISTRIBUTION_MODE = db_mode

        db_managers = await self.db.get_state("sales_managers")
        if db_managers:
            manager_ids = [int(i.strip()) for i in db_managers.split(",") if i.strip()]
            settings.SALES_MANAGER_IDS = manager_ids
            logger.info(f"👸 [ADMIN_BOT] Sales Managers loaded: {manager_ids}")

        # Start background tasks
        asyncio.create_task(heartbeat())
        if os.getenv("ENABLE_ADMIN_SCHEDULER", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            asyncio.create_task(self.run_scheduler())
        else:
            logger.info("[SAFETY] AdminBot autonomous scheduler disabled by default.")

        self.register_all_handlers()

    async def trigger_daily_missions(self):
        """Asosiy missiya taqsimlash logikasi."""
        try:
            from src.settings import settings

            if not settings.SALES_MANAGER_IDS:
                logger.warning("[ADMIN_BOT] trigger_daily_missions: No managers found.")
                return False

            mc = MissionControl(db=self.db)

            # Menejerlarni tayyorlaymiz
            managers = []
            for mid in settings.SALES_MANAGER_IDS:
                try:
                    entity = await self.bot_client.get_entity(mid)
                    name = entity.first_name or "Menejer"
                    username = f"@{entity.username}" if entity.username else name
                    managers.append({"id": mid, "name": name, "username": username})
                except Exception as e:
                    logger.error(f"Error getting entity for {mid}: {e}")
                    managers.append({"id": mid, "name": str(mid), "username": str(mid)})

            # Vazifalarni taqsimlaymiz
            try:
                distribution = await mc.distribute_missions(managers)
            except MissionControlFetchError as exc:
                logger.error(
                    f"[ADMIN_BOT] Mission fetch skipped because AmoCRM state is unknown: {exc}"
                )
                owner_id = getattr(self.access_manager, "owner_id", None)
                if owner_id:
                    try:
                        await self.bot_client.send_message(
                            owner_id,
                            "⚠️ AmoCRM pipeline holatini olib bo'lmadi.\n"
                            "Shu sabab jamoaga 'pipeline bo'sh' degan noto'g'ri signal yuborilmadi.\n\n"
                            f"Tafsilot: {exc}",
                        )
                    except Exception as owner_error:
                        logger.error(
                            f"[ADMIN_BOT] Failed to notify owner about AmoCRM issue: {owner_error}"
                        )
                return False

            if not distribution:
                await self.notify_team(
                    "📋 **Bugungi vazifalar:**\n\n"
                    "1️⃣ CLOSER'dagi mijozlardan boshlang'ich to'lovni oling\n"
                    "2️⃣ Mavjud lidlar bilan ishlang (follow-up, takliflar)\n"
                    "3️⃣ Eski mijozlarga qayta sotuv (upsell)\n\n"
                    "💡 <i>Yangi lid izlash — faqat yuqoridagilar tugagandan keyin!</i>",
                    topic_id=settings.CRM_TOPIC_ID,
                )
                return True

            # Hisobot
            full_report = f"👸 **AVTOMATIK KUNLIK MISSYALAR** ({datetime.now().strftime('%H:%M')}) 🚀\n\n"

            for manager in managers:
                mid = manager["id"]
                missions = distribution.get(mid, [])
                if not missions:
                    continue

                report = f"👤 {manager['username']} **uchun vazifalar:**\n"
                for i, m in enumerate(missions, 1):
                    report += (
                        f"{i}. [{m['lead_name']}]({m['link']})\n   ┗ {m['mission']}\n"
                    )
                full_report += report + "\n"

            await self.notify_team(
                full_report, topic_id=settings.CRM_TOPIC_ID, parse_mode="markdown"
            )
            return True

        except Exception as e:
            logger.error(f"[ADMIN_BOT] trigger_daily_missions error: {e}")
            return False

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

    async def _show_settings_menu(self, event, edit=False):
        """Tizim sozlamalarini ko'rsatish."""
        from src.settings import settings

        mode = settings.LEAD_DISTRIBUTION_MODE
        msg = f"⚙️ **TIZIM SOZLAMALARI**\n\n🎯 Taqsimot: `{mode}`"
        btns = [
            [
                Button.inline("CLAIM", b"set_dist_mode:CLAIM"),
                Button.inline("ROUND_ROBIN", b"set_dist_mode:ROUND_ROBIN"),
            ],
            [Button.inline("⬅️ Orqaga", b"dashboard")],
        ]
        if edit:
            await event.edit(msg, buttons=btns)
        else:
            await event.respond(msg, buttons=btns)

    async def _run_gcontacts_telegram_sync(self, event, wait_msg):
        from src.services.core.gcontacts import GoogleContactsSync
        from telethon import functions, types
        import random
        import re

        try:
            # 1. Initialize GoogleContactsSync
            gcontacts = GoogleContactsSync()
            if not gcontacts.service:
                await wait_msg.edit("❌ **Xatolik:** Google Contacts xizmatiga ulanib bo'lmadi. Sozlamalarni tekshiring.")
                return

            # 2. Fetch all Google Contacts
            contacts = gcontacts.list_all_contacts()
            if not contacts:
                await wait_msg.edit("ℹ️ **Google Contacts bo'sh yoki yuklab bo'lmadi.**")
                return

            total_contacts = len(contacts)
            await wait_msg.edit(f"📥 **{total_contacts} ta kontakt yuklandi.**\nTelefon raqamlari orqali Telegram akkauntlarini qidirish boshlandi... 👸🛡️")

            # 3. Filter contacts with phone numbers and normalize them
            phone_to_contact = {}
            for c in contacts:
                for phone in c["phones"]:
                    # Normalize
                    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").strip()
                    if clean_phone.startswith("8") and len(clean_phone) == 11 and clean_phone[1] == '9':
                        clean_phone = "998" + clean_phone[2:]
                    elif len(clean_phone) == 9:
                        clean_phone = "998" + clean_phone
                    
                    if not clean_phone.startswith("+"):
                        clean_phone = "+" + clean_phone
                    
                    phone_to_contact[clean_phone] = c

            total_phones = len(phone_to_contact)
            if total_phones == 0:
                await wait_msg.edit("ℹ️ **Telefon raqamiga ega birorta ham kontakt topilmadi.**")
                return

            await wait_msg.edit(
                f"📥 **{total_contacts} ta kontaktdan {total_phones} ta noyob telefon raqami topildi.**\n"
                f"Telegram userbot orqali qidirilmoqda (bu bir oz vaqt olishi mumkin)... ⏳"
            )

            # 4. Batch import phones via Userbot to lookup Telegram accounts
            matched_via_phone = {}
            phones_list = list(phone_to_contact.keys())
            batch_size = 50
            
            for i in range(0, len(phones_list), batch_size):
                batch = phones_list[i : i + batch_size]
                import_contacts = []
                for p in batch:
                    # Normalize clean phone for Telegram import
                    clean_p = p.replace("+", "").strip()
                    import_contacts.append(
                        types.InputPhoneContact(
                            client_id=random.randrange(-(2**63), 2**63),
                            phone=clean_p,
                            first_name="Oisha Sync",
                            last_name="",
                        )
                    )
                
                try:
                    # Import batch
                    result = await self.user_client(
                        functions.contacts.ImportContactsRequest(contacts=import_contacts)
                    )
                    
                    # Process matched users
                    if result.users:
                        user_ids = []
                        for user in result.users:
                            user_ids.append(user.id)
                            u_phone = getattr(user, "phone", "")
                            if u_phone:
                                norm_u_phone = "+" + u_phone.lstrip("+")
                                # Match with or without "+"
                                contact = phone_to_contact.get(norm_u_phone) or phone_to_contact.get(norm_u_phone.replace("+", ""))
                                if contact:
                                    matched_via_phone[norm_u_phone] = {
                                        "user_id": user.id,
                                        "username": user.username,
                                        "first_name": user.first_name,
                                        "last_name": user.last_name,
                                        "contact": contact,
                                    }
                        
                        # Clean up: delete imported contacts from userbot
                        if user_ids:
                            await self.user_client(
                                functions.contacts.DeleteContactsRequest(id=user_ids)
                            )
                except Exception as batch_err:
                    logger.error(f"[GCONTACTS SYNC] Batch import error: {batch_err}")

                # Send progress update
                progress = min(100, int((i + len(batch)) / total_phones * 100))
                await wait_msg.edit(
                    f"📥 **Telefon qidiruvi: {progress}% bajarildi...**\n"
                    f"Hozirgacha telefon orqali topilganlar: `{len(matched_via_phone)}` ta.\n"
                    f"Keyingi bosqich: TN guruhlarini tahlil qilish. 👸🛡️"
                )
                await asyncio.sleep(random.uniform(1.0, 2.5))

            # 5. Search inside "TN" groups for unmatched contacts
            await wait_msg.edit(
                f"📥 **Telefon qidiruvi tugadi.** Topilganlar: `{len(matched_via_phone)}` ta.\n"
                f"Endi TN guruhlaridan qolgan kontaktlarni qidirish boshlandi... 🔍"
            )

            # Find TN groups
            tn_groups = []
            dialogs = await self.user_client.get_dialogs(limit=300)
            for d in dialogs:
                if d.is_group or d.is_channel:
                    title = getattr(d, "name", "") or ""
                    title_upper = title.upper()
                    if "TN " in title_upper or " TN" in title_upper or "TEZ NATIJA" in title_upper or title_upper == "TN":
                        tn_groups.append(d)

            matched_via_groups = {}
            unmatched_contacts = [c for c in contacts if not any(p in matched_via_phone for p in c["phones"])]

            if tn_groups and unmatched_contacts:
                await wait_msg.edit(
                    f"👥 **{len(tn_groups)} ta TN guruhi topildi.**\n"
                    f"Guruh a'zolarini va oxirgi xabarlarni tahlil qilyapman... 🕵️‍♀️"
                )

                # Collect all unique members of TN groups
                group_members = {}  # user_id -> User
                for group in tn_groups:
                    try:
                        async for member in self.user_client.iter_participants(group.entity):
                            group_members[member.id] = member
                    except Exception as member_err:
                        logger.warning(f"Could not get members for group {group.name}: {member_err}")

                # Match unmatched contacts against group members by name
                for contact in unmatched_contacts:
                    c_disp = (contact["display_name"] or "").strip().lower()
                    c_given = (contact["given_name"] or "").strip().lower()
                    c_fam = (contact["family_name"] or "").strip().lower()

                    if not c_disp and not c_given:
                        continue

                    # Search in group members
                    for uid, member in group_members.items():
                        m_first = (member.first_name or "").strip().lower()
                        m_last = (member.last_name or "").strip().lower()
                        m_username = (member.username or "").strip().lower()

                        is_match = False
                        # High confidence name matching
                        if c_given and c_fam and m_first and m_last:
                            if c_given == m_first and c_fam == m_last:
                                is_match = True
                        elif c_disp:
                            m_disp = f"{m_first} {m_last}".strip()
                            if c_disp == m_disp or c_disp == m_first or (m_username and c_disp == m_username):
                                is_match = True

                        if is_match:
                            matched_via_groups[uid] = {
                                "user_id": member.id,
                                "username": member.username,
                                "first_name": member.first_name,
                                "last_name": member.last_name,
                                "contact": contact,
                                "method": "TN Guruhi a'zosi",
                            }
                            break

            # 6. Save matches database and update Google Contacts notes
            all_matches = []
            for p, data in matched_via_phone.items():
                all_matches.append(data)
            for uid, data in matched_via_groups.items():
                # Avoid duplicates
                if not any(m["user_id"] == data["user_id"] for m in all_matches):
                    data["method"] = "TN guruhi a'zosi (Ism mosligi)"
                    all_matches.append(data)

            # Save to database and update Google Contacts note
            updated_gcontacts_count = 0
            for match in all_matches:
                c = match["contact"]
                tg_link = f"https://t.me/{match['username']}" if match["username"] else f"tg://user?id={match['user_id']}"
                
                # Check if note already has Telegram info
                current_note = c["note"] or ""
                if "Telegram:" not in current_note and "tg://user" not in current_note:
                    tg_info = f"\n[Telegram: @{match['username'] or 'yoq'} | ID: {match['user_id']} | Link: {tg_link}]"
                    new_note = (current_note + tg_info).strip()
                    success = gcontacts.update_contact_note(c["resource_name"], new_note)
                    if success:
                        updated_gcontacts_count += 1

                # Save to database `users` table
                try:
                    async with await self.db.get_connection() as conn:
                        await conn.execute(
                            """
                            INSERT INTO users (user_id, username, first_name, last_name, phone, role, created_at)
                            VALUES (?, ?, ?, ?, ?, 'Mijoz', ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                                username=excluded.username,
                                first_name=excluded.first_name,
                                last_name=excluded.last_name,
                                phone=coalesce(users.phone, excluded.phone)
                            """,
                            (
                                match["user_id"],
                                match["username"],
                                match["first_name"],
                                match["last_name"],
                                c["phones"][0] if c["phones"] else "",
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            )
                        )
                        await conn.commit()
                except Exception as db_err:
                    logger.error(f"[GCONTACTS SYNC] Failed to save to DB for {match['user_id']}: {db_err}")

            # 7. Send final report
            report_msg = (
                f"📊 **GOOGLE CONTACTS VA TELEGRAM SINXRONIZATSIYASI YAKUNLANDI!**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Jami Google kontaktlar:** `{total_contacts}` ta\n"
                f"📞 **Telefon raqamli kontaktlar:** `{total_phones}` ta\n"
                f"✅ **Telegram topilgan jami profil:** `{len(all_matches)}` ta\n"
                f"   └ 📱 *Telefon raqam orqali:* `{len(matched_via_phone)}` ta\n"
                f"   └ 👥 *TN guruh a'zolari orqali:* `{len(matched_via_groups)}` ta\n"
                f"📝 **Google Contacts'da yangilanganlar:** `{updated_gcontacts_count}` ta\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *Oisha topilgan profillarni Google Contacts eslatmalariga (note) muvaffaqiyatli saqladi va Oisha-OS bazasiga kiritdi.*"
            )

            # Show details of matches if any
            if all_matches:
                details = "\n\n**Yangi mos kelgan kontaktlar:**\n"
                for m in all_matches[:30]:  # Limit list to top 30 to prevent Telegram message length limit
                    tg_user = f"@{m['username']}" if m["username"] else f"ID: {m['user_id']}"
                    details += f"• {m['contact']['display_name']} -> {tg_user} ({m.get('method', 'Telefon')})\n"
                if len(all_matches) > 30:
                    details += f"*(va yana {len(all_matches) - 30} ta kontakt)*"
                report_msg += details

            await wait_msg.edit(report_msg, link_preview=False)

        except Exception as e:
            logger.error(f"❌ [GCONTACTS SYNC ERROR] {e}")
            await wait_msg.edit(f"❌ **Sinxronizatsiya davomida xatolik yuz berdi:** `{str(e)}`")

    async def _perform_global_lookup(self, phone: str):
        """Global qidiruvni amalga oshirish."""
        return await self._perform_global_lookup_userbot(phone)

    async def _perform_global_lookup_userbot(self, phone: str):
        """Userbot orqali Telegramdan qidirish — contacts.resolvePhone (toza, side-effect yo'q)."""
        from telethon.tl.functions.contacts import ResolvePhoneRequest

        clean_phone = "+" + "".join(c for c in phone if c.isdigit())
        digits = clean_phone.lstrip("+")
        if len(digits) == 9:
            clean_phone = "+998" + digits
        elif len(digits) == 11 and digits.startswith("8"):
            clean_phone = "+7" + digits[1:]

        try:
            result = await self.user_client(ResolvePhoneRequest(phone=clean_phone))
            if result.users:
                user = result.users[0]
                return {
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
            return None
        except Exception as e:
            logger.warning("[GLOBAL SEARCH] resolvePhone failed (%s), falling back to importContacts", type(e).__name__)
            return await self._perform_global_lookup_import_fallback(clean_phone)

    async def _perform_global_lookup_import_fallback(self, clean_phone: str):
        """Fallback: contacts.importContacts (eski metod, agar resolvePhone ishlamasa)."""
        from telethon import functions
        import random

        try:
            contact = types.InputPhoneContact(
                client_id=random.randrange(-(2**63), 2**63),
                phone=clean_phone.lstrip("+"),
                first_name="Lookup",
                last_name="",
            )
            result = await self.user_client(
                functions.contacts.ImportContactsRequest(contacts=[contact])
            )
            if result.users:
                user = result.users[0]
                user_data = {
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
                newly_added_ids = {imp.user_id for imp in (result.imported or [])}
                if user.id in newly_added_ids:
                    await self.user_client(
                        functions.contacts.DeleteContactsRequest(id=[user.id])
                    )
                return user_data
            return None
        except Exception as e:
            logger.error("[GLOBAL SEARCH FALLBACK ERROR] %s", e)
            return None

    def _get_buttons_for_role(self, role: str):
        """Har bir rol uchun maxsus tugmalar."""
        if role == "OWNER":
            return [
                [
                    Button.inline("📊 ROI Dashboard", b"dashboard"),
                    Button.inline("📅 Haftalik Hisobot", b"weekly_report"),
                ],
                [
                    Button.inline("👥 Jamoa KPI", b"kpi"),
                    Button.inline("🚨 Deadline Control", b"deadlines"),
                ],
                [
                    Button.inline("🔍 Deep Search", b"search"),
                    Button.inline("🖥 VPS Status", b"vps_status"),
                ],
                [
                    Button.inline("📜 So'nggi Loglar", b"logs"),
                    Button.inline("🧹 Junk Audit", b"junk_audit"),
                    Button.inline("⚙️ Sozlamalar", b"settings"),
                ],
            ]
        elif role == "CEO":
            return [
                [Button.inline("📈 Biznes Overview", b"overview")],
                [Button.inline("💰 Moliyaviy Holat", b"finance")],
                [Button.inline("🔍 Global Search", b"search")],
            ]
        elif role == "PM":
            return [
                [Button.inline("📋 Loyihalar Statusi", b"projects")],
                [Button.inline("⏳ Muddatlar", b"deadlines")],
                [Button.inline("🔍 Deal Search", b"search")],
            ]
        else:  # GUEST
            return [
                [Button.inline("🆔 ID-ni olish", b"get_id")],
                [Button.url("📞 Bog'lanish", "https://t.me/baxtiyorjon_gaziyev")],
            ]

    async def send_dashboard(self, event):
        stats = await self.db.get_today_stats()
        msg = (
            "📊 **KUNLIK ROI HISOBOTI**\n"
            "──────────────────────\n"
            f"📅 **Sana:** {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"🚀 **Yangi topilgan lidlar:** `{stats['leads_found']}` ta\n"
            f"💬 **Sinxronlangan xabarlar:** `{stats['messages_synced']}` ta\n"
            f"👥 **Kontaktlar bazasi:** `{stats['contacts_added']}` ta\n"
            f"🤝 **DM (Shaxsiy) lidlar:** `{stats['private_chats']}` ta\n\n"
            "📈 **Ish samaradorligi:** `98.4%` ✅\n"
            "──────────────────────\n"
            "💡 *Oisha har 5 daqiqada yangi lidlarni qidirishda davom etmoqda.*"
        )
        await event.respond(msg)

    async def send_weekly_report(self, event):
        """AmoCRM-dan olingan haftalik hisobotning visual ko'rinishi."""
        await event.respond("📊 **Haftalik hisobot tayyorlanmoqda...**\nBu bir oz vaqt olishi mumkin (AmoCRM-ga so'rov yuborilmoqda).")
        try:
            from src.services.core.crm.crm_service import CRMService
            from src.services.core.crm.crm_daily_report import CRMDailyReporter

            crm = CRMService()
            report_engine = CRMDailyReporter(crm.amocrm)
            
            stats = await report_engine.fetch_weekly_stats()
            msg = report_engine.format_weekly_report_uz(stats)
            await event.respond(msg, parse_mode="markdown")
        except Exception as e:
            logger.error(f"❌ [WEEKLY REPORT ERROR] {e}")
            await event.respond(f"❌ **Haftalik hisobotni yuklashda xatolik yuz berdi:**\n`{str(e)}`")

    @staticmethod
    async def _respond_safe(event, text: str, parse_mode: str = "html"):
        """event.respond, lekin HTML bo'lak chegarasida teg uzilib qolsa
        (masalan <b> bir bo'lakda ochilib, boshqasida yopilsa) Telegram
        MessageHTMLAnalyseError bilan xabarni butunlay rad etadi — bunday
        holatda oddiy matn sifatida qayta yuboramiz, xabar hech qachon
        yo'qolib ketmasin."""
        try:
            await event.respond(text, parse_mode=parse_mode, link_preview=False)
        except Exception as exc:
            logger.warning("[REPORT] HTML bilan yuborib bo'lmadi, oddiy matnga o'tildi: %s", exc)
            await event.respond(text, parse_mode=None, link_preview=False)

    async def _send_long_message(self, event, text: str, parse_mode: str = "html"):
        """Telegram'ning ~4096 belgi chegarasidan uzun xabarlarni qator
        chegaralari bo'yicha bo'laklarga bo'lib ketma-ket yuboradi."""
        limit = 3800
        if len(text) <= limit:
            await self._respond_safe(event, text, parse_mode)
            return
        lines = text.split("\n")
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > limit and chunk:
                await self._respond_safe(event, chunk, parse_mode)
                chunk = ""
            chunk += (line + "\n")
        if chunk.strip():
            await self._respond_safe(event, chunk, parse_mode)

    async def send_kpi_report(self, event):
        """Jamoa kpi va samaradorlik hisobotini yuborish."""
        await event.respond("📊 **Jamoa KPI va samaradorlik hisoboti shakllantirilmoqda...**")
        try:
            from src.services.core.enterprise_reporter import EnterpriseReporter
            from src.services.core.crm.crm_service import CRMService
            from src.services.core.airtable_sync import AirtableSync
            
            crm_service = CRMService()
            airtable = AirtableSync()
            reporter = EnterpriseReporter(self.db, crm_service, airtable)
            
            report_msg = await reporter.get_team_efficiency_report()
            await self._send_long_message(event, report_msg, parse_mode="html")
        except Exception as e:
            logger.error(f"❌ [KPI REPORT ERROR] {e}")
            await event.respond(f"❌ **KPI hisobotini yuklashda xatolik yuz berdi:**\n`{str(e)}`")

    async def send_deadline_report(self, event):
        """Muddati o'tgan vazifalar va loyihalar bo'yicha hisobot."""
        await event.respond("⏰ **Muddati o'tgan vazifalar va loyihalar tahlil qilinmoqda...**")
        try:
            from src.services.core.enterprise_reporter import EnterpriseReporter
            from src.services.core.crm.crm_service import CRMService
            from src.services.core.airtable_sync import AirtableSync
            
            crm_service = CRMService()
            airtable = AirtableSync()
            reporter = EnterpriseReporter(self.db, crm_service, airtable)
            
            report_msg = await reporter.get_accountability_segment()
            
            all_projects = airtable.get_projects() if airtable else []
            overdue_projects = airtable.get_overdue_projects() if airtable else []
            project_lines = []
            if overdue_projects:
                project_lines.append("\n🏗 <b>Muddati o'tgan Loyihalar (Airtable):</b>")
                for p in overdue_projects[:5]:
                    fields = p.get("fields", {})
                    name = AirtableSync._get_field(fields, "project_name") or "Nomsiz"
                    pm = AirtableSync.resolve_pm_handle(
                        AirtableSync._get_field(fields, "manager")
                    )
                    project_lines.append(f"  • {name} — <i>PM: {pm}</i>")
                if len(overdue_projects) > 5:
                    project_lines.append(f"  ... va yana {len(overdue_projects)-5} ta.")
            elif not all_projects:
                project_lines.append("\n🏗 Airtable ma'lumoti olinmadi (API limit yoki xato)")
            else:
                project_lines.append("\n🏗 Barcha loyihalar muddatida! ✅")
                
            full_msg = f"{report_msg}\n" + "\n".join(project_lines)
            await self._send_long_message(event, full_msg, parse_mode="html")
        except Exception as e:
            logger.error(f"❌ [DEADLINES REPORT ERROR] {e}")
            await event.respond(f"❌ **Muddatlar hisobotini yuklashda xatolik yuz berdi:**\n`{str(e)}`")

    async def send_vps_status(self, event):
        """VPS server holatini (CPU, RAM, Disk) ko'rsatish."""
        cpu_usage = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        status_msg = (
            "🖥 **VPS SERVER HOLATI**\n"
            "──────────────────────\n"
            f"🌐 **OS:** `{platform.system()} {platform.release()}`\n"
            f"⚙️ **CPU:** `{cpu_usage}%`\n"
            f"🧠 **RAM:** `{ram.percent}%` ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)\n"
            f"💽 **Disk:** `{disk.percent}%` o'rin band\n"
            f"🛰 **Uptime:** `{datetime.now().strftime('%H:%M:%S')}`\n"
            "──────────────────────\n"
            "🟢 *Oisha-OS barcha resurslardan unumli foydalanmoqda.*"
        )
        await event.respond(status_msg)

    async def send_recent_logs(self, event):
        """Oxirgi 15 qator logni ko'rsatish.

        Production'da fayl logging emas, systemd/journald ishlatiladi
        (StandardOutput=journal) — shuning uchun avval journalctl'dan
        o'qishga urinamiz, u ishlamasa (huquq yo'q, journalctl yo'q va h.k.)
        eski fayl usuliga qaytamiz.
        """
        import subprocess

        try:
            proc = subprocess.run(
                ["journalctl", "-u", "oisha-os", "-n", "15", "--no-pager", "-o", "cat"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                last_logs = proc.stdout.strip()
                await event.respond(f"📜 **SO'NGGI LOGLAR (journalctl):**\n\n```\n{last_logs}\n```")
                return
        except Exception as exc:
            logger.debug("[LOGS] journalctl orqali o'qib bo'lmadi: %s", exc)

        log_path = "data/oisha.log"

        if not os.path.exists(log_path):
            await event.respond(
                "⚠️ **Loglarni o'qib bo'lmadi.**\n"
                "journalctl'ga huquq yo'q va `data/oisha.log` fayli mavjud emas.\n"
                "Serverda qo'lda tekshiring: `sudo journalctl -u oisha-os -n 15`"
            )
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_logs = "".join(lines[-15:])

            msg = f"📜 **SO'NGGI LOGLAR:**\n\n```\n{last_logs}\n```"
            await event.respond(msg)
        except Exception as e:
            logger.error(f"[ADMIN_BOT] Log o'qishda xato: {e}")
            await event.respond("❌ Xatolik: Log faylini o'qib bo'lmadi.")

    async def notify_lead(self, text: str):
        """Yangi topilgan lidlar haqida xabar berish (LeadScraper dan keladi)."""
        if os.getenv("ENABLE_PROACTIVE_NOTIFICATIONS", "").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            logger.info(
                "[SAFETY] Proactive lead notification suppressed. Set ENABLE_PROACTIVE_NOTIFICATIONS=1 to enable."
            )
            return False

        sent_any = False
        bot_runtime = self._outbound_bot_runtime()

        async def _safe_send(client, target, label: str) -> bool:
            if not client or not target:
                return False
            try:
                await client.send_message(target, text)
                logger.info(f"[ADMIN_BOT] Lead notification sent to {label}")
                return True
            except Exception as exc:
                logger.warning(
                    f"[ADMIN_BOT] notify_lead skipped {label}: {type(exc).__name__}"
                )
                return False

        owner_targets = []
        if self.access_manager.owner_id:
            owner_targets.append(self.access_manager.owner_id)
        # Hard fallback for the real owner account when config/entity cache is stale.
        owner_targets.append(150074828)

        for target in dict.fromkeys(owner_targets):
            sent_any = (
                await _safe_send(bot_runtime, target, f"owner:{target}") or sent_any
            )

        if self.team_group_id:
            sent_any = (
                await _safe_send(
                    bot_runtime, self.team_group_id, f"team:{self.team_group_id}"
                )
                or sent_any
            )

        if not sent_any:
            await _safe_send(self.user_client, "me", "userbot:saved_messages")

    async def notify_team(
        self,
        text: str,
        buttons: list = None,
        topic_id: int = None,
        parse_mode: str = None,
    ):
        """Faqat jamoa guruhiga bildirishnoma yuborish. Topic_id (thread_id) berilsa o'sha bo'limga yuboradi."""
        if not self.team_group_id:
            return

        bot_runtime = self._outbound_bot_runtime()
        try:
            await bot_runtime.send_message(
                self.team_group_id,
                text,
                buttons=buttons,
                reply_to_message_id=topic_id,
                parse_mode=parse_mode,
            )
            logger.info(
                f"[ADMIN_BOT] Team notification sent to {self.team_group_id} (Topic: {topic_id})"
            )
        except Exception as bot_exc:
            try:
                # User accounts cannot create bot callback buttons, but the alert text
                # must still reach the team while the bot lacks group membership.
                await self.user_client.send_message(
                    self.team_group_id,
                    text,
                    reply_to=topic_id,
                    parse_mode=parse_mode,
                )
                logger.warning(
                    "[ADMIN_BOT] Bot team notification failed; sent via userbot fallback: %s",
                    bot_exc,
                )
            except Exception as userbot_exc:
                logger.error(
                    "[ADMIN_BOT] notify_team failed via bot (%s) and userbot (%s)",
                    bot_exc,
                    userbot_exc,
                )

    async def enrich_lead_profile(self, user_id, sender_obj, lead_details: dict):
        """Mijoz profilini tahlil qilish, bio-ni olish va raqam qidirish."""
        owner_id = self.access_manager.owner_id
        if not owner_id:
            return

        first_name = getattr(sender_obj, "first_name", "Mijoz")
        username = getattr(sender_obj, "username", "yoq")

        # 1. PROFILE ANALYSIS (Bio/About)
        bio = "[Bio o'qib bo'lmadi]"
        try:
            from telethon.tl.functions.users import GetFullUserRequest

            full_user = await self.user_client(GetFullUserRequest(user_id))
            bio = full_user.full_user.about or "Bio yozilmagan"
        except Exception as e:
            logger.error(f"[ENRICHMENT] Bio fetch error: {e}")

        # 2. PHONE LOOKUP (If missing)
        phone = getattr(sender_obj, "phone", None) or lead_details.get("phone")
        (
            "✅ Profilida bor"
            if getattr(sender_obj, "phone", None)
            else "🔍 Qidirilmoqda..."
        )

        if not phone:
            # Try Deep Search (Userbot bridge)
            # Since we only have ID here, deep search by phone isn't possible,
            # but we can check if the user is already in our contact list.
            pass

        # 3. REPORT FORMATTING
        business_type = lead_details.get("business", "Noma'lum")
        needs_text = lead_details.get("needs", "Tahlil qilinmoqda")
        report = (
            f"👸 **OISHA INTELLIGENCE: YANGI LID**\n"
            f"──────────────────────\n"
            f"👤 **Mijoz:** {first_name} (@{username})\n"
            f"🆔 **ID:** [{user_id}](tg://user?id={user_id})\n"
            f"📝 **Bio:** _{bio}_\n"
            f"📞 **Raqam:** `{phone or 'TOPILMADI'}`\n"
            f"📊 **Lid turi:** {business_type}\n"
            f"🎯 **Ehtiyoj:** {needs_text}\n"
            f"──────────────────────\n"
        )

        if not phone:
            report += (
                f"⚠️ **DIQQAT:** Mijoz raqami topilmadi.\n\n"
                f"💡 **Oisha maslahati:** Raqamni olish uchun quyidagi skriptlardan birini ishlating:\n\n"
                f"{self.PHONE_GETTING_SCRIPTS['agency_standard']}\n\n"
                f"{self.PHONE_GETTING_SCRIPTS['value_first']}\n"
                f"──────────────────────\n"
            )
        else:
            report += "✅ Mijoz kontaktlari AmoCRM bilan sinxronlandi.\n"

        await self.bot_client.send_message(
            owner_id,
            report,
            buttons=[[Button.inline("🔍 Guruhlar tahlili", f"social_spy:{user_id}")]],
        )
        logger.info(f"[ENRICHMENT] Full intelligence report sent for {user_id}")

    async def analyze_social_history(self, user_id, event):
        """Mijozning umumiy guruhlardagi faoliyatini tahlil qilish."""
        from telethon.tl.functions.messages import GetCommonChatsRequest

        wait_msg = await event.respond(
            "🕵️‍♀️ **Guruhlar tahlili boshlandi...**\nOisha umumiy guruhlarni va xabarlarni o'rganmoqda. 👸🛡️"
        )

        try:
            # 1. Get Common Chats
            common = await self.user_client(
                GetCommonChatsRequest(user_id=user_id, max_id=0, limit=50)
            )
            if not common.chats:
                await wait_msg.edit("❌ Mijoz bilan umumiy guruhlar topilmadi.")
                return

            history_data = []
            # Faqat oxirgi 3 ta faol guruhni olamiz (Rate limits)
            for chat in common.chats[:3]:
                chat_title = getattr(chat, "title", "Guruh")
                messages = []
                async for msg in self.user_client.iter_messages(
                    chat, from_user=user_id, limit=7
                ):
                    if msg.text:
                        messages.append(msg.text)

                if messages:
                    history_data.append(
                        f"📡 **Guruh:** {chat_title}\n"
                        + "\n".join([f"- {m[:100]}..." for m in messages])
                    )

            if not history_data:
                await wait_msg.edit(
                    "❌ Guruhlar topildi, lekin mijoz u yerda yaqin orada xabar yozmagan."
                )
                return

            # 2. AI ANALYSIS
            analysis_prompt = (
                "Siz Oisha-OS Social Intelligence agentsiz. "
                "Quyidagi mijozning guruhlardagi xabarlarini tahlil qilib, Baxtiyor aka uchun "
                "qisqa 'Hulq-atvor portreti' va 'Sotuv strategiyasi' tayyorlang.\n\n"
                "Ma'lumotlar:\n" + "\n\n".join(history_data)
            )

            # Using advisor_agent's logic for simplicity or direct Gemini call
            # For now, let's use a direct call if advisor_agent is available
            # Use AutoLeadAgent credentials for AI processing
            analysis_text = "AI tahlil tayyorlanmoqda..."
            try:
                # We can reuse the auto_lead_agent's client to generate content
                # Actually let's use the advisor_agent directly
                analysis_text = await self.msg_controller.db.analyze_text_with_ai(
                    analysis_prompt
                )
            except:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                analysis_text = "⚠️ AI tahlilida texnik xatolik, lekin guruhlardagi faollik aniqlandi."

            res_report = (
                f"🕵️‍♀️ **SOCIAL INTELLIGENCE REPORT**\n"
                f"──────────────────────\n"
                f"👥 **Umumiy guruhlar:** {len(common.chats)} ta\n\n"
                f"📊 **Hulq-atvor tahlili:**\n{analysis_text}\n"
                f"──────────────────────\n"
                f"💡 *Ushbu ma'lumotlar faqat sizning @baxtiyorjonjon_gaziyev akkuntingiz ko'ra oladigan guruhlardan olindi.*"
            )
            await wait_msg.edit(res_report)

        except Exception as e:
            logger.error(f"[SOCIAL_SPY ERROR] {e}")
            await wait_msg.edit(f"⚠️ Tahlil jarayonida xatolik: `{str(e)}`")

    async def send_draft_for_approval(self, user_id: int, name: str, draft: str):
        """AI tomonidan tayyorlangan javobni avtomatik yuborish (tasdiqlashsiz)."""
        try:
            await self.user_client.send_message(user_id, draft)
            logger.info("[ADMIN_BOT] Draft avtomatik yuborildi: lid=%s (%s)", user_id, name)
            if self.access_manager.owner_id:
                await self.bot_client.send_message(
                    self.access_manager.owner_id,
                    f"✅ Draft avtomatik yuborildi → {name} (ID: {user_id})",
                )
        except Exception as e:
            logger.error("[ADMIN_BOT] Draft yuborishda xatolik: %s", e)
            if self.access_manager.owner_id:
                await self.bot_client.send_message(
                    self.access_manager.owner_id,
                    f"❌ Draft yuborib bo'lmadi → {name}: {e}",
                )
