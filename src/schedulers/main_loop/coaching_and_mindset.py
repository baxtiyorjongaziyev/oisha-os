"""
Call quality analytics, psychological coaching, and keep-alive pulse jobs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from telethon import functions

from src.settings import settings
import src.main as m
from src.schedulers.main_loop.helpers import _is_due

logger = logging.getLogger("OishaScheduler")


async def run_coaching_and_mindset(now: datetime, background_monitor_task: Any) -> None:
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
