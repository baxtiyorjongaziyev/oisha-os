"""
Scheduled job execution helpers for Admin Bot.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def run_morning_briefing_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("👸 [SCHEDULER] Morning Briefing boshlandi...")
    try:
        from src.services.core.proactive_worker import send_morning_briefing

        await send_morning_briefing()
        await db.set_state(job_id, "done")
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


async def run_daily_plan_job(db: Any, job_id: str, phase: str, api_server_module: Any) -> None:
    logger.info(f"[SCHEDULER] Daily plan discipline phase={phase}...")
    try:
        from src.services.core.proactive_worker import demand_daily_plans

        sent = await demand_daily_plans(phase)
        await db.set_state(job_id, "done")
        if sent:
            api_server_module.add_activity(
                "📝 Daily Plan Discipline",
                f"Kunlik plan bo'yicha {phase} faza yuborildi.",
                "success",
            )
    except Exception as e:
        logger.error(f"[DAILY PLAN ERROR] {e}")
        api_server_module.add_activity(
            "⚠️ Daily Plan Error", str(e), "error"
        )


async def run_daily_missions_job(admin_bot: Any, db: Any, job_id: str, current_time: str, api_server_module: Any) -> None:
    logger.info(f"👸 [SCHEDULER] Mission Distribution {current_time}...")
    try:
        await admin_bot.trigger_daily_missions()
        await db.set_state(job_id, "done")
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


async def run_client_journey_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("[SCHEDULER] Client Journey Excellence boshlandi...")
    try:
        from src.services.core.proactive_worker import check_client_journey_excellence

        sent = await check_client_journey_excellence()
        await db.set_state(job_id, "done")
        if sent:
            api_server_module.add_activity(
                "🌟 Client Journey",
                "Mijoz yo'li bo'yicha wow-service mikromanagement report yuborildi.",
                "success",
            )
    except Exception as e:
        logger.error(f"[CLIENT JOURNEY ERROR] {e}")
        api_server_module.add_activity(
            "⚠️ Client Journey Error", str(e), "error"
        )


async def run_lunch_reminder_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("👸 [SCHEDULER] Lunch Reminder boshlandi...")
    try:
        from src.services.core.proactive_worker import send_lunch_reminder

        await send_lunch_reminder()
        await db.set_state(job_id, "done")
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


async def run_evening_fact_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("👸 [SCHEDULER] Evening Fact Report boshlandi...")
    try:
        from src.services.core.proactive_worker import send_evening_fact_report

        await send_evening_fact_report()
        await db.set_state(job_id, "done")
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


async def run_night_shift_job(admin_bot: Any, db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("👸 [SCHEDULER] Night Shift CRM Cleanup boshlandi...")
    api_server_module.add_activity(
        "🧹 Night Shift",
        "AmoCRM dublikatlar va qotib qolgan lidlar tozalanmoqda...",
        "thinking",
    )
    try:
        if admin_bot.night_shift:
            await admin_bot.night_shift.run_cleanup()
        await db.set_state(job_id, "done")
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


async def run_intelligence_audit_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("👸 [SCHEDULER] Intelligence Audit boshlandi (tungi)...")
    api_server_module.add_activity(
        "🕵️ Intelligence Audit",
        "Tungi AI tahlili boshlandi. Faollik loglari o'rganilmoqda...",
        "thinking",
    )
    try:
        from src.services.core.audit_agent import AuditAgent
        import src.config as config

        _audit = AuditAgent(api_key=config.GEMINI_API_KEY, db=db)
        report = await _audit.generate_audit_report(limit=200)
        from src.api_server import user_client as uc

        if uc:
            try:
                await uc.send_message(
                    "me",
                    f"🦉 **OISHA: Tungi Intelligence Audit**\n\n{report}",
                )
            except Exception as entity_error:
                logger.error(f"[AUDIT PEER ERROR] {entity_error}")
                await uc.send_message(
                    "me",
                    f"🦉 **OISHA: Tungi Intelligence Audit**\n\n{report}",
                )
        await db.set_state(job_id, "done")
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


async def run_junk_audit_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("👸 [SCHEDULER] Junk Leads Audit boshlandi...")
    api_server_module.add_activity(
        "🧹 Junk Audit",
        "CRM bekorchi sdelkalar tahlili boshlandi...",
        "thinking",
    )
    try:
        from src.services.core.proactive_worker import send_junk_leads_report

        await send_junk_leads_report()
        await db.set_state(job_id, "done")
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


async def run_scorecard_job(db: Any, job_id: str, api_server_module: Any) -> None:
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
        await db.set_state(job_id, "done")
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


async def run_stagnation_job(db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("[SCHEDULER] Sales Conversion Push boshlandi...")
    try:
        from src.services.core.proactive_worker import check_amocrm_stagnation
        import src.config as config

        await check_amocrm_stagnation()
        from src.services.core.sales_analytics import SalesAnalytics
        from telegram import Bot

        bot_token = getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "CRM_GROUP_ID", None)
        thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
        if bot_token and group_id:
            tg_bot = Bot(token=bot_token)
            analytics = SalesAnalytics(bot=tg_bot)
            await analytics.send_stagnation_alert(group_id, thread_id)
        await db.set_state(job_id, "done")
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


async def run_juma_job(admin_bot: Any, db: Any, job_id: str, api_server_module: Any) -> None:
    logger.info("🕌 [SCHEDULER] Juma Mubarak outreach boshlandi...")
    try:
        if admin_bot.juma_notifier:
            await admin_bot.juma_notifier.check_and_send()
        await db.set_state(job_id, "done")
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


async def run_funnel_job(db: Any, job_id: str, api_server_module: Any) -> None:
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
        await db.set_state(job_id, "done")
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
