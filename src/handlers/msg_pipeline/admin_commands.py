"""
Admin commands and checkpoint advancement pipeline handler.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from telethon import events

from src.settings import settings
from src.context import app_ctx

logger = logging.getLogger("OishaMsgPipeline")

async def advance_checkpoint(event, msg_controller) -> None:
    """Per-chat checkpoint'ni advance qilish — boot_catchup uchun."""
    try:
        chat_id = getattr(event, "chat_id", None)
        msg_id = getattr(getattr(event, "message", None), "id", None) or getattr(
            event, "id", None
        )
        if chat_id and msg_id and msg_controller is not None:
            await msg_controller.db.update_chat_checkpoint(chat_id, msg_id)
    except Exception as exc:
        logger.debug("[CHECKPOINT] update skipped: %s", exc)


# ---------------------------------------------------------------------------
# 2. Admin Commands
# ---------------------------------------------------------------------------

async def process_admin_commands(
    event,
    *,
    client: "TelegramClient",
    bot_client,
    msg_controller,
    settings,
    meeting_scheduler,
    get_surgical_integration,
    _negotiation_int,
    lead_scraper,
    audit_agent,
    auto_lead_agent,
    admin_bot,
    TN5_GROUP_ID,
    TN5_TOPIC_ID,
) -> bool:
    """
    Admin buyruqlarini qayta ishlash.
    Qaytaradi: True = buyruq bajarildi (handler to'xtatilsin), False = davom etish.
    """
    if not (event.is_private and event.message.text and event.message.text.startswith("/")):
        return False

    text = event.message.text

    if text.startswith("/voice_approve"):
        from src.api_server import approve_voice_call

        parts = text.split()
        if len(parts) != 2:
            await event.respond("Foydalanish: /voice_approve <lead_id>")
            return True
        ok = await approve_voice_call(parts[1])
        await event.respond(
            "✅ Voice Agent chaqiruvi tasdiqlandi va navbatga qo'yildi." if ok
            else "⚠️ Bu lead uchun kutilayotgan chaqiruv topilmadi."
        )
        return True

    if text.startswith("/voice_reject"):
        from src.api_server import reject_voice_call

        parts = text.split()
        if len(parts) != 2:
            await event.respond("Foydalanish: /voice_reject <lead_id>")
            return True
        ok = await reject_voice_call(parts[1])
        await event.respond(
            "🚫 Voice Agent chaqiruvi rad etildi." if ok
            else "⚠️ Bu lead uchun kutilayotgan chaqiruv topilmadi."
        )
        return True

    if text == "/sync_backlog":
        await event.respond(
            "👸 Oisha-OS: O'tmishdagi (Backlog) xabarlarni skanerlashni boshladim... 👸🛡️"
        )
        asyncio.create_task(
            lead_scraper.sync_topic_to_contacts(
                client=client,
                group_id=TN5_GROUP_ID,
                topic_id=TN5_TOPIC_ID,
                limit=50,
            )
        )
        return True

    if text == "/force_sync_all":
        await event.respond(
            "👸 Oisha-OS: Guruhning barcha a'zolarini ommaviy saqlash rejimini tasdiqladim!\n"
            "Bu jarayon kunlab davom etishi mumkin. Orqa fonda (parallel) xavfsiz tezlikda saqlayman... 🐢🛡️"
        )
        asyncio.create_task(
            lead_scraper.sync_all_group_members(
                client=client, group_id=TN5_GROUP_ID
            )
        )
        return True

    if text == "/efficiency":
        from src.services.core.airtable_sync import AirtableSync

        at_sync = AirtableSync()
        msg_controller.enterprise_reporter.airtable = at_sync

        report = await msg_controller.enterprise_reporter.get_team_efficiency_report()
        await event.respond(report, parse_mode="markdown")
        return True

    if text == "/report":
        await event.respond("⏳ Oisha-OS: Kunlik hisobot (Reportagram) tayyorlanmoqda...")
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter

            amocrm_client = None
            if msg_controller and getattr(msg_controller, "crm", None):
                amocrm_client = getattr(msg_controller.crm, "amocrm", None)
            if not amocrm_client:
                amocrm_client = get_surgical_integration().amocrm

            reporter = CRMDailyReporter(amocrm=amocrm_client)
            stats = await reporter.fetch_stats()
            prev = reporter._load_prev_stats()
            report_text = reporter.format_report(stats, prev)
            await event.respond(report_text)
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            await event.respond(f"❌ Xatolik yuz berdi: {e}")
        return True

    if text == "/stats":
        await event.respond("⏳ Joriy statistika olinmoqda...")
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter

            amocrm_client = None
            if msg_controller and getattr(msg_controller, "crm", None):
                amocrm_client = getattr(msg_controller.crm, "amocrm", None)
            if not amocrm_client:
                amocrm_client = get_surgical_integration().amocrm

            reporter = CRMDailyReporter(amocrm=amocrm_client)
            stats = await reporter.fetch_stats()
            report_text = (
                f"📊 **Bugungi holat ({stats.date_label})**\n"
                f"Tushgan: {stats.total_leads} lead\n"
                f"Gaplashilgan: {stats.contacted} lead\n"
                f"Sifatli: {stats.qualified} lead\n"
                f"Muvaffaqiyatli (Won): {stats.won}\n"
                f"Daromad: ${stats.revenue:,.0f}\n"
                f"Pipeline qiymati: ${stats.pipeline_value:,.0f}"
            )
            await event.respond(report_text)
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            await event.respond(f"❌ Xatolik: {e}")
        return True

    if text == "/history":
        try:
            from src.services.core.crm.crm_daily_report import CRMDailyReporter

            reporter = CRMDailyReporter(amocrm=None)
            history = reporter.get_history(7)
            if not history:
                await event.respond("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
                return True
            lines = ["📅 **So'nggi 7 kunlik hisobotlar tarixi:**"]
            for s in history:
                lines.append(
                    f"• {s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
                )
            await event.respond("\n".join(lines))
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            await event.respond(f"❌ Xatolik: {e}")
        return True

    if text == "/audit":
        await event.respond(
            "👸 Oisha-OS: Oxirgi harakatlaringizni tahlil qilyapman, bir oz kutib turing... 👸📈📊"
        )
        report = await audit_agent.generate_audit_report(limit=100)
        await event.respond(report)
        return True

    if text == "/audit_leads":
        await event.respond(
            "👸 Oisha-OS: Oxirgi 100 ta dialogni audit qilyapman, shaffoflik hisoboti tayyor bo'lishi bilan yuboraman... 👸🛡️"
        )

        audit_report = "👸 **Oisha-OS Lead Audit (Transparency Report)** 👸\n\n"
        async for dialog in client.iter_dialogs(limit=100):
            if not dialog.is_user or dialog.entity.bot:
                continue

            name = getattr(dialog.entity, "first_name", "User")
            messages = []
            async for msg in client.iter_messages(dialog.id, limit=5):
                if msg.text:
                    messages.append(msg.text)

            if not messages:
                continue

            lead_data = await auto_lead_agent.extract_lead_info(
                "\n".join(reversed(messages)), {"id": dialog.id, "first_name": name}
            )

            if lead_data and lead_data.get("is_lead"):
                audit_report += f"✅ **{name}** — Lead deb topildi. ({lead_data.get('business', 'Noʻmalum')})\n"
            else:
                audit_report += f"❌ **{name}** — Shaxsiy/Irrelevant deb topildi.\n"

            if len(audit_report) > 3500:
                await event.respond(audit_report)
                audit_report = ""

        if audit_report:
            await event.respond(audit_report)
        return True

    if text.startswith("/find "):
        phone = text.split(" ", 1)[1].strip()
        await event.respond(
            f"🔍 **{phone}** raqamini butun Telegramdan qidiryapman... 👸🛡️"
        )
        from src.utils.phone_lookup import global_phone_lookup

        user_data = await global_phone_lookup(phone)
        if user_data:
            username = (
                f"@{user_data['username']}"
                if user_data["username"]
                else "Mavjud emas"
            )
            response = (
                f"✅ **Foydalanuvchi topildi!**\n\n"
                f"👤 **Ism:** {user_data['first_name']} {user_data['last_name'] or ''}\n"
                f"🆔 **ID:** `{user_data['user_id']}`\n"
                f"🔗 **Username:** {username}\n"
                f"📱 **Raqam:** `{phone}`"
            )
            await event.respond(response)
        else:
            await event.respond(
                "❌ **Afsus, foydalanuvchi topilmadi.**\n"
                "(Ehtimol, foydalanuvchi o'z maxfiylik sozlamalarida raqam orqali qidiruvni cheklagan bo'lishi mumkin)."
            )
        return True

    if text == "/sync_today":
        await event.respond(
            "👸 Oisha-OS: Kecha va bugungi shaxsiy suhbatlarni (DM) skanerlashni boshladim... 👸🛡️"
        )
        asyncio.create_task(
            lead_scraper.sync_private_dialogs(client=client, limit=100)
        )
        return True

    if text == "/hunt":
        await event.respond(
            "👸 Oisha-OS: 2026-yildagi BARCHA shaxsiy yozishmalarni skanerlash boshlandi!\n"
            "🎯 Sifatli leadlar Team CRM topicga yuboriladi.\n"
            "⏳ Bu jarayon 10-30 daqiqa olishi mumkin..."
        )
        asyncio.create_task(
            lead_scraper.hunt_2026_leads(
                client=client,
                bot_client=bot_client,
            )
        )
        return True

    if text == "/sync_history":
        await event.respond(
            "👸 Oisha-OS: O'tgan 1 yillik shaxsiy yozishmalarni (DM) bazaga kiritishni boshladim... 👸🛡️\n"
            "Bu biroz vaqt olishi mumkin, orqa fonda xavfsiz ishlayman."
        )
        from src.services.core.historical_sync import HistoricalSyncService

        sync_service = HistoricalSyncService(msg_controller.db, client)
        asyncio.create_task(sync_service.start_backlog_sync(days=365))
        return True

    return False
