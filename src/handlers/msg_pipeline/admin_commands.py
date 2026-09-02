"""
Admin commands and checkpoint advancement pipeline handler.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any


logger = logging.getLogger("OishaMsgPipeline")


async def advance_checkpoint(event, msg_controller) -> None:
    """Per-chat checkpoint'ni advance qilish — boot_catchup uchun."""
    try:
        chat_id = getattr(event, "chat_id", None)
        msg_id = getattr(getattr(event, "message", None), "id", None) or getattr(event, "id", None)
        if chat_id and msg_id and msg_controller is not None:
            await msg_controller.db.update_chat_checkpoint(chat_id, msg_id)
    except Exception as exc:
        logger.debug("[CHECKPOINT] update skipped: %s", exc)


async def _handle_voice_commands(event: Any, text: str) -> bool:
    if text.startswith("/voice_approve"):
        from src.api_server import approve_voice_call
        parts = text.split()
        if len(parts) != 2:
            await event.respond("Foydalanish: /voice_approve <lead_id>")
            return True
        ok = await approve_voice_call(parts[1])
        await event.respond("✅ Voice Agent chaqiruvi tasdiqlandi va navbatga qo'yildi." if ok else "⚠️ Bu lead uchun kutilayotgan chaqiruv topilmadi.")
        return True

    if text.startswith("/voice_reject"):
        from src.api_server import reject_voice_call
        parts = text.split()
        if len(parts) != 2:
            await event.respond("Foydalanish: /voice_reject <lead_id>")
            return True
        ok = await reject_voice_call(parts[1])
        await event.respond("🚫 Voice Agent chaqiruvi rad etildi." if ok else "⚠️ Bu lead uchun kutilayotgan chaqiruv topilmadi.")
        return True
    return False


async def _handle_sync_and_scraper(event: Any, text: str, client: Any, lead_scraper: Any, group_id: Any, topic_id: Any) -> bool:
    if text == "/sync_backlog":
        await event.respond("👸 Oisha-OS: O'tmishdagi (Backlog) xabarlarni skanerlashni boshladim... 👸🛡️")
        if lead_scraper:
            asyncio.create_task(lead_scraper.sync_topic_to_contacts(client=client, group_id=group_id, topic_id=topic_id, limit=50))
        return True
    if text == "/force_sync_all":
        await event.respond("👸 Oisha-OS: Guruhning barcha a'zolarini ommaviy saqlash rejimini tasdiqladim!")
        if lead_scraper:
            asyncio.create_task(lead_scraper.sync_all_group_members(client=client, group_id=group_id))
        return True
    return False


async def _handle_reports(event: Any, text: str, msg_controller: Any, get_surgical_integration: Any) -> bool:
    if text == "/efficiency" and msg_controller:
        from src.services.core.airtable_sync import AirtableSync
        msg_controller.enterprise_reporter.airtable = AirtableSync()
        report = await msg_controller.enterprise_reporter.get_team_efficiency_report()
        await event.respond(report, parse_mode="markdown")
        return True

    if text in ("/report", "/stats"):
        await event.respond("⏳ Oisha-OS: Ma'lumot tayyorlanmoqda...")
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter
            amo = getattr(msg_controller.crm, "amocrm", None) if (msg_controller and getattr(msg_controller, "crm", None)) else get_surgical_integration().amocrm
            reporter = CRMDailyReporter(amocrm=amo)
            stats = await reporter.fetch_stats()
            if text == "/report":
                report_text = reporter.format_report(stats, reporter._load_prev_stats())
            else:
                report_text = f"📊 **Bugungi holat ({stats.date_label})**\nTushgan: {stats.total_leads} | Gaplashilgan: {stats.contacted} | Sifatli: {stats.qualified} | Won: {stats.won} | Daromad: ${stats.revenue:,.0f}"
            await event.respond(report_text)
        except Exception as e:
            logger.error("[ADMIN_CMD] Report error: %s", e)
            await event.respond(f"❌ Xatolik: {e}")
        return True
    return False


async def _handle_audit_and_extra(event: Any, text: str, audit_agent: Any, auto_lead_agent: Any, meeting_scheduler: Any) -> bool:
    if text == "/audit" and audit_agent:
        await event.respond("👸 Oisha-OS: Oxirgi harakatlaringiz tahlil qilinmoqda...")
        report = await audit_agent.generate_audit_report(limit=100)
        await event.respond(report)
        return True
    if text == "/audit_leads" and auto_lead_agent:
        await event.respond("👸 Oisha-OS: Barcha yangi lidlar tahlil qilinmoqda...")
        report = await auto_lead_agent.audit_and_report_all()
        await event.respond(report)
        return True
    if text == "/meetings" and meeting_scheduler:
        report = await meeting_scheduler.get_upcoming_meetings_report()
        await event.respond(report)
        return True
    return False


async def process_admin_commands(
    event,
    *,
    client: Any,
    bot_client: Any,
    msg_controller: Any,
    settings: Any,
    meeting_scheduler: Any,
    get_surgical_integration: Any,
    _negotiation_int: Any,
    lead_scraper: Any,
    audit_agent: Any,
    auto_lead_agent: Any,
    admin_bot: Any,
    TN5_GROUP_ID: Any,
    TN5_TOPIC_ID: Any,
) -> bool:
    """Admin commands processor."""
    if not (event.is_private and event.message.text and event.message.text.startswith("/")):
        return False
    text = event.message.text.strip()
    if await _handle_voice_commands(event, text):
        return True
    if await _handle_sync_and_scraper(event, text, client, lead_scraper, TN5_GROUP_ID, TN5_TOPIC_ID):
        return True
    if await _handle_reports(event, text, msg_controller, get_surgical_integration):
        return True
    if await _handle_audit_and_extra(event, text, audit_agent, auto_lead_agent, meeting_scheduler):
        return True
    return False
