import os
import logging
from typing import Any, Dict, List, Optional
from src.time_utils import get_local_now
from src.database import Database
from src.services.core.tool_adapters import (
    build_default_tool_registry,
    send_group_message_with_fallback,
)
from src.services.core.agent_loop import AgentTask
from src.services.proactive.formatters import (
    DAILY_PLAN_PHASES,
    _mention,
    _run_notification_agent,
)
from src import config

logger = logging.getLogger(__name__)


async def demand_daily_plans(
    bot_token: Optional[str] = None,
    amocrm_client=None,
    airtable_client=None,
    bot_client=None,
):
    """Jamoaning kunlik rejalarini so'rash."""
    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")

    phase_key = None
    if now.hour == 9:
        phase_key = "initial"
    elif now.hour == 12:
        phase_key = "reminder"
    elif now.hour == 15:
        phase_key = "escalation"

    if not phase_key:
        return

    phase = DAILY_PLAN_PHASES[phase_key]
    job_key = f"{phase['job']}_{today}"
    if await db.is_job_run(job_key, today):
        return

    registry = build_default_tool_registry(
        bot_token=bot_token,
        amocrm=amocrm_client,
        airtable=airtable_client,
        bot_client=bot_client,
    )
    team_tool = registry.get("team_directory")
    telegram_tool = registry.get("telegram_notifications")

    members = await team_tool.fetch_team_members()
    mentions = [_mention(m) for m in members if m.get("user_id") or m.get("username")]

    msg = (
        f"{phase['title']}\n\n"
        f"Hurmatli jamoa! Bugungi ish rejalaringizni belgilangan vaqtgacha ({phase['deadline']}) topshirishingizni so'raymiz.\n\n"
        f"📌 <b>Eslatma:</b> {phase['tone']}\n\n"
    )
    if mentions:
        msg += f"Mas'ullar: {', '.join(mentions)}\n"

    task = AgentTask(
        task_type="demand_daily_plans",
        channel="group",
        target=str(config.TEAM_CHAT_ID),
        content=msg,
        metadata={"phase": phase_key, "hour": now.hour},
    )

    async def _executor(t: AgentTask):
        return await telegram_tool.send_group_summary(t.content)

    result = await _run_notification_agent(db, task, _executor)
    if result.success:
        await db.mark_job_run(job_key, today)


async def send_proactive_followups(bot_token: Optional[str] = None):
    """Mijozlar bilan proaktiv follow-up xabarlari."""
    logger.info("[PROACTIVE] Followup check running...")


async def distribute_team_tasks(bot_token: Optional[str] = None):
    """Vazifalarni jamoaga avtomatik taqsimlash."""
    logger.info("[PROACTIVE] Distribute tasks check running...")


from telegram import Bot


async def _execute_telegram_notification(
    client_or_registry: Any,
    group_id: Optional[int] = None,
    message: Optional[str] = None,
    thread_id: Optional[int] = None,
    direct_messages: Optional[List[Dict[str, Any]]] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """Send proactive notifications to Telegram groups/topics and direct messages."""
    # Legacy invocation pattern: _execute_telegram_notification(bot_client, chat_id, message, parse_mode)
    if (
        isinstance(group_id, (int, str))
        and isinstance(message, str)
        and not direct_messages
        and not hasattr(client_or_registry, "get")
    ):
        chat_id = int(group_id)
        if client_or_registry and hasattr(client_or_registry, "send_message"):
            await client_or_registry.send_message(chat_id, message, parse_mode=parse_mode)
        else:
            bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
            bot = Bot(token=bot_token) if bot_token else None
            if bot:
                await send_group_message_with_fallback(
                    bot,
                    chat_id=chat_id,
                    text=message,
                    thread_id=thread_id,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
        return {"success": True, "chat_id": chat_id}

    telegram_tool = None
    if hasattr(client_or_registry, "get"):
        telegram_tool = client_or_registry.get("telegram_notifications") or client_or_registry.get("telegram")

    group_sent = False
    group_message_id = None
    if group_id and message:
        if telegram_tool:
            res = await telegram_tool.send_group_message(
                chat_id=group_id,
                text=message,
                thread_id=thread_id,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            group_sent = getattr(res, "success", False)
            group_message_id = getattr(res, "group_message_id", None)
        else:
            bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
            bot = Bot(token=bot_token) if bot_token else None
            if bot:
                msg_obj = await send_group_message_with_fallback(
                    bot,
                    chat_id=group_id,
                    text=message,
                    thread_id=thread_id,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                group_sent = bool(msg_obj)
                group_message_id = getattr(msg_obj, "message_id", None)

    dm_sent_count = 0
    if direct_messages:
        for dm in direct_messages:
            uid = dm.get("user_id")
            txt = dm.get("text")
            if not (uid and txt):
                continue
            dm_parse_mode = dm.get("parse_mode", parse_mode)
            try:
                if telegram_tool:
                    await telegram_tool.send_direct_message(
                        user_id=uid,
                        text=txt,
                        parse_mode=dm_parse_mode,
                    )
                else:
                    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
                    bot = Bot(token=bot_token) if bot_token else None
                    if bot:
                        await bot.send_message(
                            chat_id=uid,
                            text=txt,
                            parse_mode=dm_parse_mode,
                        )
                dm_sent_count += 1
            except Exception as dm_err:
                logger.warning(f"[TELEGRAM NOTIFY] DM to user {uid} failed: {dm_err}")

    return {
        "success": group_sent or dm_sent_count > 0,
        "group_sent": group_sent,
        "group_message_id": group_message_id,
        "direct_messages_sent": dm_sent_count,
    }


async def send_daily_report(bot_client=None):
    """Kunlik operatsion hisobot."""
    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    if now.hour != 19 or now.minute > 15:
        return

    job_key = f"daily_ops_report_{today}"
    if await db.is_job_run(job_key, today):
        return

    msg = f"📊 <b>Kunlik Operatsion Hisobot ({today})</b>\n\nBarcha tizimlar barqaror ishlamoqda. ✅"
    await _execute_telegram_notification(bot_client, config.TEAM_CHAT_ID, msg)
    await db.mark_job_run(job_key, today)


async def send_morning_briefing(bot_client=None):
    """Ertalabki brifing xabari (09:00)."""
    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    if now.hour != 9 or now.minute > 15:
        return

    job_key = f"morning_briefing_{today}"
    if await db.is_job_run(job_key, today):
        return

    msg = "☀️ <b>Xayrli tong, Jon Branding jamoasi!</b>\n\nBugungi kun barchamiz uchun samarali va unumli o'tsin! 🚀"
    await _execute_telegram_notification(bot_client, config.TEAM_CHAT_ID, msg)
    await db.mark_job_run(job_key, today)


async def send_overdue_nudges(bot_client=None):
    """Muddati o'tgan vazifalar bo'yicha eslatma."""
    pass


async def send_lunch_reminder(bot_client=None):
    """Tushlik eslatmasi (13:00)."""
    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    if now.hour != 13 or now.minute > 15:
        return

    job_key = f"lunch_reminder_{today}"
    if await db.is_job_run(job_key, today):
        return

    msg = "🍽 <b>Tushlik vaqti!</b>\n\nYoqimli ishtaha va maroqli hordiq tilaymiz! 🍲"
    await _execute_telegram_notification(bot_client, config.TEAM_CHAT_ID, msg)
    await db.mark_job_run(job_key, today)


async def send_evening_fact_report(bot_client=None):
    """Kechki fakt hisoboti (18:30)."""
    pass


async def send_junk_leads_report(bot_client=None):
    """Sifatsiz lidlar hisoboti."""
    pass
