"""
Telegram message event handler, self commands, and negotiation parser.
"""
import asyncio
import logging
import os
from typing import Any, Dict, Optional
from telethon import events

from src.settings import settings
from src.context import app_ctx
from src.entrypoint.filters import (
    _userbot_private_replies_disabled,
    _is_private_userbot_event,
    _should_block_private_userbot_reply,
    _is_personal_folder_sender,
)
from src.entrypoint.crm_push import (
    push_block_to_amocrm,
    global_phone_lookup,
    notify_admin,
    run_autonomous_advice,
)
from src.entrypoint.daemon_tasks import spawn_task

logger = logging.getLogger("OishaMsgEvent")

async def handle_new_message(event):
    """Barcha kiruvchi xabarlarni xavfsizlik va aqllilik bilan tahlil qilish."""
    from src.api.live_monitor import broadcast_event

    # 0. Botning o'z ID sini olish (Sikl oldini olish uchun)
    me = await client.get_me()
    await safe_responder.update_me_id(me.id)

    # Broadcast: incoming message
    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", "User")
    msg_text = (event.message.message or "")[:200]
    chat_title = getattr(event.chat, "title", None) or sender_name
    await broadcast_event({
        "type": "message",
        "chat_id": event.chat_id,
        "chat_name": chat_title,
        "sender": sender_name,
        "text": msg_text,
        "is_private": event.is_private,
        "message_id": event.id,
    })

    # [PHASE 1.6] Advance per-chat checkpoint BEFORE any filtering.
    from src.handlers.message_handler import advance_checkpoint
    await advance_checkpoint(event, app_ctx.msg_controller)

    if _should_block_private_userbot_reply(event):
        logger.info("[USERBOT] Personal DM ignored by policy chat=%s", event.chat_id)
        return

    # 1. Spamdan himoya va Guruh filtrini tekshirish
    if not await safe_responder.should_respond(event):
        return

    # 1.5 Real-time Lead Sync (Automatic for TN5 Topic 7)
    if (
        event.chat_id == TN5_GROUP_ID
        and getattr(event.message.reply_to, "reply_to_msg_id", None) == TN5_TOPIC_ID
    ):
        logger.info(
            f"[ENTERPRISE SYNC] New lead detected from Topic 7! MessageID: {event.id}"
        )
        # Run sync in parallel using the unified LeadScraper logic
        asyncio.create_task(sync_single_lead(event))
        await broadcast_event({"type": "sync", "text": f"Lead sync boshlandi: {event.id}", "chat_id": event.chat_id})
        return

    # 1.6 Admin Commands
    from src.handlers.message_handler import process_admin_commands
    if await process_admin_commands(
        event,
        client=client,
        bot_client=bot_client,
        msg_controller=app_ctx.msg_controller,
        settings=settings,
        meeting_scheduler=meeting_scheduler,
        get_surgical_integration=get_surgical_integration,
        _negotiation_int=_negotiation_int,
        lead_scraper=lead_scraper,
        audit_agent=audit_agent,
        auto_lead_agent=auto_lead_agent,
        admin_bot=admin_bot,
        TN5_GROUP_ID=TN5_GROUP_ID,
        TN5_TOPIC_ID=TN5_TOPIC_ID,
    ):
        return

    # 2. Xabar matnini olish
    message_text = event.message.message
    chat_id = event.chat_id
    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", "User")
    non_customer_reason = detect_non_customer_context(message_text)
    personal_folder_sender = await _is_personal_folder_sender(sender)

    logger.info(
        f"[USERBOT] Processing message from {sender_name} in {chat_id}: {message_text[:50]}..."
    )

    # ── HISOBCHI AI: Card bot xabarlari ──────────────────────────────────
    from src.handlers.message_handler import process_hisobchi
    if await process_hisobchi(
        event,
        client=client,
        sender=sender,
        message_text=message_text,
        msg_controller=app_ctx.msg_controller,
        voice_processor=voice_processor,
        settings=settings,
    ):
        await broadcast_event({"type": "system", "text": f"Hisobchi AI qayta ishladi: {sender_name}", "chat_id": event.chat_id})
        return
    # ─────────────────────────────────────────────────────────────────────

    if event.is_private and not event.out and message_text:
        try:
            await app_ctx.msg_controller.db.log_message(sender.id, message_text, is_ai=False)
            
            # [AMOCRM SYNC] Add to SessionManager
            import sys
            if 'src.main' in sys.modules and hasattr(sys.modules['src.main'], 'session_manager'):
                phone = getattr(sender, 'phone', None)
                sys.modules['src.main'].session_manager.add_message(sender.id, sender_name, message_text, phone)

            # [WAZZUP ALTERNATIVE] Push to AmoCRM Native Chat
            if getattr(settings, 'AMOCRM_CHAT_SECRET', None):
                from src.services.core.crm.amocrm_chat import AmoCRMChatClient
                chat_client = AmoCRMChatClient(
                    amocrm_account_id=settings.AMOCRM_CHAT_ACCOUNT_ID,
                    channel_id=settings.AMOCRM_CHAT_CHANNEL_ID,
                    channel_secret=settings.AMOCRM_CHAT_SECRET
                )
                asyncio.create_task(
                    chat_client.send_message_to_amocrm(
                        user_id=sender.id,
                        chat_id=chat_id,
                        text=message_text,
                        sender_name=sender_name,
                        phone=getattr(sender, 'phone', None)
                    )
                )

            # [AUTONOMOUS ADVISOR] Real-time Analysis
            asyncio.create_task(
                run_autonomous_advice(chat_id, sender_name, message_text)
            )

        except Exception as log_ex:
            logger.error(f"[USERBOT] Failed to log incoming message: {log_ex}")

    # 3. New Message Logic (Elite Intake)
    if personal_folder_sender:
        logger.info(f"[ELITE INTAKE] Personal/family folder skipped: {sender_name}")
    elif non_customer_reason:
        logger.info(
            f"[ELITE INTAKE] Non-customer context skipped: {sender_name} reason={non_customer_reason}"
        )
    elif event.is_private and not event.out and not getattr(sender, "bot", False):
        from src.handlers.message_handler import process_elite_intake
        await process_elite_intake(
            event,
            sender=sender,
            message_text=message_text,
            sender_name=sender_name,
            msg_controller=app_ctx.msg_controller,
            auto_lead_agent=auto_lead_agent,
            folder_manager=folder_manager,
            admin_bot=admin_bot,
            bot_client=bot_client,
            welcome_manager=app_ctx.welcome_manager,
            TN5_GROUP_ID=TN5_GROUP_ID,
        )

    # [GOD MODE] Multi-Modal (Voice Note) Handling — Gemini STT + Surgical Assessment
    if event.is_private and not event.out and event.message.voice and voice_processor:
        from src.handlers.message_handler import process_voice
        await process_voice(
            event,
            client=client,
            sender=sender,
            sender_name=sender_name,
            msg_controller=app_ctx.msg_controller,
            voice_processor=voice_processor,
            admin_bot=admin_bot,
            surgical_integration=surgical_integration,
            auto_reply_gate=auto_reply_gate,
        )

    # [GOD MODE] Media/Document Sync
    if (
        event.is_private
        and not event.out
        and (event.message.photo or event.message.document)
    ):
        from src.handlers.message_handler import process_media
        await process_media(
            event,
            client=client,
            sender_name=sender_name,
            msg_controller=app_ctx.msg_controller,
            admin_bot=admin_bot,
            voice_processor=voice_processor,
        )

    # 2.5 Tiered Auto-Reply Gate (shadow/vip_only/live + kill-switch)
    from src.handlers.message_handler import process_ai_reply
    await process_ai_reply(
        event,
        client=client,
        sender=sender,
        chat_id=chat_id,
        sender_name=sender_name,
        message_text=message_text,
        msg_controller=app_ctx.msg_controller,
        auto_reply_gate=auto_reply_gate,
        safe_responder=safe_responder,
        scouter=app_ctx.scouter,
        surgical_integration=surgical_integration,
        action_parser=action_parser,
        admin_bot=admin_bot,
    )
    await broadcast_event({"type": "reply", "text": f"AI reply jo'natildi: {sender_name}", "chat_id": chat_id})


async def self_command_handler(event):
    """Handle commands from the owner in 'Saved Messages'."""
    from src.api.live_monitor import broadcast_event
    if not event.message.text:
        return
    cmd = event.message.text.lower().strip()

    handler, prefix = get_command_handler(cmd)
    if handler:
        await broadcast_event({"type": "command", "text": f"Buyruq: {cmd}", "chat_id": "saved_messages"})
        ctx = {
            "app_ctx.msg_controller": app_ctx.msg_controller,
            "client": client,
            "bot_client": bot_client,
            "settings": settings,
            "meeting_scheduler": meeting_scheduler,
            "get_surgical_integration": get_surgical_integration,
            "_negotiation_int": _negotiation_int,
        }
        await handler(event, **ctx)
        return

    # Command not found — do nothing


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

