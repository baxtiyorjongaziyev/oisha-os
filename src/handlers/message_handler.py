"""
handle_new_message helper funksiyalari — main.py dan ajratilgan.

Usage:
    from src.handlers.message_handler import (
        advance_checkpoint,
        process_admin_commands,
        process_hisobchi,
        process_elite_intake,
        process_voice,
        process_media,
        process_ai_reply,
    )
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.events import NewMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Checkpoint
# ---------------------------------------------------------------------------

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
            from src.services.core.crm_daily_report import CRMDailyReporter

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
            await event.respond(f"❌ Xatolik yuz berdi: {e}")
        return True

    if text == "/stats":
        await event.respond("⏳ Joriy statistika olinmoqda...")
        try:
            from src.services.core.crm_daily_report import CRMDailyReporter

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
            await event.respond(f"❌ Xatolik: {e}")
        return True

    if text == "/history":
        try:
            from src.services.core.crm_daily_report import CRMDailyReporter

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
        from src.services.enterprise.historical_sync import HistoricalSyncService

        sync_service = HistoricalSyncService(msg_controller.db, client)
        asyncio.create_task(sync_service.start_backlog_sync(days=365))
        return True

    return False


# ---------------------------------------------------------------------------
# 3. Hisobchi AI
# ---------------------------------------------------------------------------

async def process_hisobchi(
    event,
    *,
    client: "TelegramClient",
    sender,
    message_text: str,
    msg_controller,
    voice_processor,
    settings,
) -> bool:
    """
    Hisobchi AI — card bot xabarlarini qayta ishlash.
    Qaytaradi: True = xabar qayta ishlandi, False = davom etish.
    """
    from src.services.core.hisobchi_handlers import (
        handle_card_bot_message,
        handle_finance_group_reply,
        is_card_bot_sender,
    )
    from src.services.core.hisobchi_engine import HisobchiEngine

    try:
        _hisobchi_engine = HisobchiEngine(msg_controller.db)

        if event.is_private and not event.out and is_card_bot_sender(sender):
            await handle_card_bot_message(event, client, _hisobchi_engine)
            return True

        if not event.out and event.message.voice and voice_processor:
            from src.services.core.hisobchi_handlers import _get_finance_config

            finance_group_id, _, _ = _get_finance_config()
            is_finance_chat = (finance_group_id is not None and event.chat_id == finance_group_id)
            is_auth_user = False
            if event.is_private:
                managers = getattr(settings, "SALES_MANAGER_IDS", [])
                sender_id = getattr(sender, "id", None)
                me = await client.get_me()
                is_auth_user = (sender_id is not None and (sender_id in managers or sender_id == me.id))
            if is_finance_chat or is_auth_user:
                from src.services.core.hisobchi_handlers import process_finance_voice_message

                was_voice_hisobchi = await process_finance_voice_message(
                    event, client, _hisobchi_engine, voice_processor
                )
                if was_voice_hisobchi:
                    return True

        if not event.is_private and not event.out and message_text:
            was_hisobchi = await handle_finance_group_reply(event, client, _hisobchi_engine)
            if was_hisobchi:
                return True
    except Exception as exc:
        logger.error("[HISOBCHI] Handler error: %s", exc, exc_info=True)

    return False


# ---------------------------------------------------------------------------
# 4. Elite Intake — lead extraction va CRM sync
# ---------------------------------------------------------------------------

async def process_elite_intake(
    event,
    *,
    sender,
    message_text: str,
    sender_name: str,
    msg_controller,
    auto_lead_agent,
    folder_manager,
    admin_bot,
    bot_client,
    welcome_manager,
    TN5_GROUP_ID,
) -> None:
    """
    Yangi DM xabarlarini tahlil qilish, lead aniqlash va CRM ga qo'shish.
    """
    lead_data = await auto_lead_agent.extract_lead_info(
        message_text, {"id": sender.id, "first_name": sender_name}
    )

    if not lead_data:
        return

    intent = lead_data.get("intent_category", "POTENTIAL")

    if folder_manager:
        asyncio.create_task(folder_manager.assign_to_folder(sender.id, intent))

    if lead_data.get("is_lead") and not await msg_controller.db.is_crm_synced(
        event.sender_id
    ):
        logger.info(
            f"[ELITE INTAKE] Yangi lid aniqlandi: {sender_name} (Intent: {intent})"
        )

        intent_label_map = {
            "HOT_LEAD": "🔥 Qaynoq mijoz",
            "WARM_LEAD": "♨️ Issiq mijoz",
            "POTENTIAL": "🌱 Potensial mijoz",
        }
        intent_label = intent_label_map.get(intent, f"🔵 {intent}")

        await msg_controller.db.upsert_user(
            sender.id,
            sender_name,
            username=getattr(sender, "username", None),
            intent=intent,
            region=lead_data.get("city"),
            business_type=lead_data.get("activity"),
            brand_name=lead_data.get("brand_name"),
        )

        if intent == "HOT_LEAD" and admin_bot:
            draft_prompt = (
                f"Mijoz: {sender_name}\n"
                f"Xabar: {event.message.text}\n\n"
                "Baxtiyor aka nomidan ushbu mijozga do'stona, lekin professional javob loyihasini tayyorlang. "
                "Unga yordam berishga tayyorligimizni va loyihasini o'rganib chiqishimizni ayting."
            )
            draft = await msg_controller.db.analyze_text_with_ai(draft_prompt)
            await admin_bot.send_draft_for_approval(
                sender.id, sender_name, draft
            )

        phone = lead_data.get("phone")
        if not phone and sender:
            phone = getattr(sender, "phone", None)
            if not phone and bot_client:
                try:
                    full_user = await bot_client.get_entity(sender.id)
                    phone = getattr(full_user, "phone", None)
                    if phone:
                        logger.info(
                            "📞 [PHONE] Telethon orqali raqam olindi: %s", sender.id
                        )
                except Exception as exc:
                    logger.debug("[PHONE] Telethon get_entity xato: %s", exc)

        if not phone:
            phone = "Raqam yo'q"

        username = getattr(sender, "username", None)
        if not username and sender and bot_client:
            try:
                if "full_user" not in locals():
                    full_user = await bot_client.get_entity(sender.id)
                username = getattr(full_user, "username", None)
                if username:
                    logger.info(
                        "[USERNAME] Telethon orqali username olindi: @%s", username
                    )
            except Exception as exc:
                logger.debug("[USERNAME] Telethon get_entity xato: %s", exc)

        if not username:
            username = "Username yo'q"

        username_str = (
            f"@{username}" if username != "Username yo'q" else username
        )
        crm_sync = await msg_controller.crm.sync_lead(
            user_id=sender.id,
            name=f"DM Lead: {sender_name}",
            phone=phone,
            note=f"AI Tahlil: {lead_data.get('needs')}\nIntent: {intent}\nUser: {username_str}",
        )
        if crm_sync.get("success"):
            await msg_controller.db.set_crm_synced(event.sender_id)

        await welcome_manager.send_welcome(event.sender_id)

        sync_line = (
            "✅ AmoCRM-ga saqlandi."
            if crm_sync.get("success")
            else f"⚠️ CRM sync xato: {crm_sync.get('error', 'nomaʼlum')}"
        )
        lead_notify_text = (
            f"👸 **Yangi Lid aniqlandi!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Ism:** {sender_name}\n"
            f"🔗 **Username:** {username_str}\n"
            f"📞 **Raqam:** {phone}\n"
            f"🎯 **Holat:** {intent_label}\n"
            f"💬 **Xabar:** {(message_text or '')[:200]}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{sync_line}"
        )
        if admin_bot:
            await admin_bot.notify_lead(lead_notify_text)

        if intent == "HOT_LEAD" and bot_client and TN5_GROUP_ID:
            try:
                await bot_client.send_message(
                    TN5_GROUP_ID, lead_notify_text, parse_mode="md"
                )
                logger.info(f"[HOT LEAD] CRM guruhiga yuborildi: {sender_name}")
            except Exception as crm_notif_err:
                logger.warning(
                    f"[HOT LEAD] CRM guruh notif xato: {crm_notif_err}"
                )


# ---------------------------------------------------------------------------
# 5. Voice — Gemini STT + Negotiation Assessment
# ---------------------------------------------------------------------------

async def process_voice(
    event,
    *,
    client: "TelegramClient",
    sender,
    sender_name: str,
    msg_controller,
    voice_processor,
    admin_bot,
    surgical_integration,
    auto_reply_gate,
) -> None:
    """Ovozli xabarlarni Gemini STT orqali qayta ishlash."""
    logger.info("🎙️ [VOICE] New voice from %s...", sender_name)
    try:
        temp_path = f"temp_voice_{event.id}.ogg"
        await client.download_media(event.message, file=temp_path)

        try:
            from src.agents.negotiation_engine import transcribe_and_assess_audio

            with open(temp_path, "rb") as f:
                audio_bytes = f.read()
            crm_status = ""
            if hasattr(msg_controller, "crm"):
                try:
                    user_info = await msg_controller.db.get_user_info(
                        event.sender_id
                    )
                    phone = user_info.get("phone") if user_info else None
                    if phone:
                        crm_status = await msg_controller.crm.get_user_context(
                            phone
                        )
                except Exception as exc:
                    logger.debug("[VOICE] CRM context lookup failed: %s", exc)

            stt_result = await transcribe_and_assess_audio(
                audio_bytes, mime_type="audio/ogg", crm_status=crm_status
            )
            transcript = stt_result.get("transcript", "")
            assessment = stt_result.get("assessment")

            if transcript:
                admin_note = f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{transcript}"
                if assessment:
                    admin_note += (
                        f"\n\n🔍 **Assessment:** stage={assessment.stage} "
                        f"| intent={assessment.intent} "
                        f"| prob={assessment.close_probability:.0%}"
                    )
                if admin_bot:
                    await admin_bot.notify_lead(admin_note)

                if (
                    surgical_integration
                    and surgical_integration.should_use_surgical(
                        str(event.sender_id), transcript
                    )
                ):
                    surgical_result = await surgical_integration.process_message(
                        str(event.sender_id),
                        transcript,
                        context={"source": "voice", "user_info": {}},
                    )
                    if surgical_result.get("mode") == "surgical":
                        voice_reply = surgical_result.get("response", "")
                        if voice_reply:
                            _voice_decision = await auto_reply_gate.evaluate(
                                msg_controller.db,
                                is_mentioned=False,
                                lead_score=0,
                                message_text=transcript or "",
                            )
                            if _voice_decision.action == "send":
                                await event.reply(voice_reply)
                                logger.info(
                                    "[VOICE→SURGICAL] Auto-replied to %s",
                                    sender_name,
                                )
                            else:
                                logger.info(
                                    "[VOICE→SURGICAL] Skipped reply (gate=%s)",
                                    _voice_decision.action,
                                )

        except Exception as stt_err:
            logger.warning("[VOICE] Gemini STT failed, fallback: %s", stt_err)
            result = await voice_processor.transcribe(temp_path)
            if result and admin_bot:
                await admin_bot.notify_lead(
                    f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{result}"
                )

        asyncio.create_task(voice_processor.cleanup(temp_path))
    except Exception as exc:
        logger.error("[VOICE] Integration error: %s", exc)


# ---------------------------------------------------------------------------
# 6. Media/Document — Google Drive upload
# ---------------------------------------------------------------------------

async def process_media(
    event,
    *,
    client: "TelegramClient",
    sender_name: str,
    msg_controller,
    admin_bot,
) -> None:
    """Media/hujjatlarni Google Drive ga yuklash."""
    logger.info("📁 [MEDIA] New media from %s...", sender_name)
    try:
        media_path = await client.download_media(event.message)
        if media_path:

            def upload_drive():
                return msg_controller.google.drive.upload_file(media_path)

            drive_link = await asyncio.to_thread(upload_drive)

            if drive_link:
                if admin_bot:
                    type_str = "Rasm" if event.message.photo else "Hujjat"
                    await admin_bot.notify_lead(
                        f"📁 **Yangi {type_str} ({sender_name}):**\n🔗 [Google Drive Link]({drive_link})"
                    )

            if os.path.exists(media_path):
                os.remove(media_path)

    except Exception as exc:
        logger.error("[MEDIA] Integration error: %s", exc)


# ---------------------------------------------------------------------------
# 7. AI Reply — auto-reply gate + surgical + legacy
# ---------------------------------------------------------------------------

async def process_ai_reply(
    event,
    *,
    client: "TelegramClient",
    sender,
    chat_id: int,
    sender_name: str,
    message_text: str,
    msg_controller,
    auto_reply_gate,
    safe_responder,
    scouter,
    surgical_integration,
    action_parser,
    admin_bot,
) -> None:
    """Auto-reply gate orqali AI javobini generatsiya qilish va yuborish."""
    try:
        is_mentioned = False
        if event.message.text:
            me = await client.get_me()
            text_low = event.message.text.lower()
            me_username = (me.username or "").lower()
            is_mentioned = bool(me_username and f"@{me_username}" in text_low)

        decision = await auto_reply_gate.evaluate(
            msg_controller.db,
            is_mentioned=is_mentioned,
            lead_score=0,
            message_text=event.message.text or "",
        )
        logger.info(
            "[AUTO_GATE] chat=%s action=%s reason=%s "
            "mode=%s kill=%s",
            chat_id,
            decision.action,
            decision.reason,
            decision.effective_mode,
            decision.kill_switch_on,
        )

        if decision.action == "skip":
            return
        if decision.action == "escalate":
            if admin_bot:
                try:
                    await admin_bot.notify_lead(
                        f"🚨 **REVIEW kerak** chat=`{chat_id}` sender={sender_name}\n"
                        f"Sabab: `{decision.reason}`\n"
                        f"Matn: {(event.message.text or '')[:500]}"
                    )
                except Exception as notify_ex:
                    logger.warning("[AUTO_GATE] escalate notify failed: %s", notify_ex)
            return

        dosye = await scouter.get_user_dosye(sender.id)

        await safe_responder.prepare_to_reply(event, client)

        ai_raw_response = None
        if surgical_integration and surgical_integration.should_use_surgical(
            str(sender.id), message_text or ""
        ):
            try:
                surgical_result = await surgical_integration.process_message(
                    user_id=str(sender.id),
                    message=message_text or "",
                    context={
                        "user_info": {
                            "first_name": getattr(sender, "first_name", ""),
                            "last_name": getattr(sender, "last_name", ""),
                            "username": getattr(sender, "username", ""),
                        },
                        "chat_id": chat_id,
                        "source": "telegram",
                    },
                )
                if surgical_result.get("mode") == "surgical":
                    ai_raw_response = surgical_result.get("response")
                    logger.info(
                        "[SURGICAL] Autonomous response uid=%s "
                        "stage=%s prob=%s",
                        sender.id,
                        surgical_result.get("deal_info", {}).get("stage"),
                        f"{surgical_result.get('deal_info', {}).get('probability', 0):.0%}",
                    )
                    if surgical_result.get("deal_info", {}).get("probability", 1) < 0.2:
                        ai_raw_response = None
            except Exception as surg_ex:
                logger.warning("[SURGICAL] Fallback to legacy: %s", surg_ex)

        if not ai_raw_response:
            ai_raw_response = await msg_controller.get_response(
                user_id=sender.id,
                user_name=sender_name,
                message=message_text,
                context={
                    "chat_id": chat_id,
                    "is_group": not event.is_private,
                    "dosye": dosye,
                },
            )

        if ai_raw_response:
            final_text = await action_parser.parse_and_execute(
                reply_text=ai_raw_response,
                sender_id=sender.id,
                sender_name=sender_name,
                username=getattr(sender, "username", "yoq"),
                saved_phone=None,
                context=None,
                is_business=False,
            )

            if final_text:
                if decision.action == "shadow":
                    if admin_bot:
                        try:
                            await admin_bot.notify_lead(
                                f"👁 **SHADOW PREVIEW** chat=`{chat_id}` sender={sender_name}\n"
                                f"Rejim: `{decision.effective_mode}` ({decision.reason})\n"
                                f"📥 User: {(event.message.text or '')[:300]}\n"
                                f"🤖 Bot draft: {final_text[:500]}"
                            )
                        except Exception as notify_ex:
                            logger.warning(
                                "[AUTO_GATE] shadow notify failed: %s", notify_ex
                            )
                    try:
                        await msg_controller.db.log_message(
                            sender.id, final_text, is_ai=True
                        )
                    except Exception as log_ex:
                        logger.error(
                            "[USERBOT] Failed to log AI reply (shadow): %s", log_ex
                        )
                    logger.info("[USERBOT] Shadow preview queued for chat %s", chat_id)
                else:
                    if event.is_private:
                        logger.info(
                            "[USERBOT] Private DM autoreply blocked for chat %s (%s)",
                            chat_id,
                            sender_name,
                        )
                    else:
                        limited, rl_reason = safe_responder.is_rate_limited(chat_id)
                        if limited:
                            logger.warning(
                                "[USERBOT] Rate-limit skip chat=%s reason=%s",
                                chat_id,
                                rl_reason,
                            )
                            if admin_bot:
                                try:
                                    await admin_bot.notify_lead(
                                        f"⏱ **RATE-LIMIT skip** chat=`{chat_id}` reason=`{rl_reason}`\n"
                                        f"Matn tayyor edi, yuborilmadi (flood oldini olish)."
                                    )
                                except Exception as exc:
                                    logger.debug("[RATE-LIMIT] Admin notify failed: %s", exc)
                        else:
                            await event.respond(final_text)
                            try:
                                await msg_controller.db.log_message(
                                    sender.id, final_text, is_ai=True
                                )
                            except Exception as log_ex:
                                logger.error("[USERBOT] Failed to log AI reply: %s", log_ex)
                            safe_responder.update_rate_limit(chat_id)
                            logger.info("[USERBOT] Replied successfully to %s", chat_id)

    except Exception as exc:
        logger.error("[USERBOT] Error while handling message: %s", exc)
