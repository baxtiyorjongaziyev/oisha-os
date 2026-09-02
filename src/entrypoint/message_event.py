"""
Telegram message event handler, self commands, and negotiation parser.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

from src.settings import settings
from src.context import app_ctx
from src.entrypoint.filters import (
    _should_block_private_userbot_reply,
    _is_personal_folder_sender,
)
from src.entrypoint.crm_push import (
    run_autonomous_advice,
)

logger = logging.getLogger("OishaMsgEvent")


async def _broadcast_incoming_message(event: Any) -> tuple[Any, str, str]:
    from src.api.live_monitor import broadcast_event
    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", "User")
    msg_text = (event.message.message or "")[:200]
    chat_title = getattr(event.chat, "title", None) or sender_name
    await broadcast_event({
        "type": "message", "chat_id": event.chat_id, "chat_name": chat_title,
        "sender": sender_name, "text": msg_text, "is_private": event.is_private, "message_id": event.id,
    })
    return sender, sender_name, msg_text


async def _sync_and_log_crm_channels(event: Any, sender: Any, sender_name: str, message_text: str, chat_id: int) -> None:
    if not (event.is_private and not event.out and message_text):
        return
    try:
        if app_ctx.msg_controller:
            await app_ctx.msg_controller.db.log_message(sender.id, message_text, is_ai=False)
        if 'src.main' in sys.modules and hasattr(sys.modules['src.main'], 'session_manager'):
            sys.modules['src.main'].session_manager.add_message(sender.id, sender_name, message_text, getattr(sender, 'phone', None))
        if getattr(settings, 'AMOCRM_CHAT_SECRET', None):
            from src.services.core.crm.amocrm_chat import AmoCRMChatClient
            chat_client = AmoCRMChatClient(
                amocrm_account_id=settings.AMOCRM_CHAT_ACCOUNT_ID,
                channel_id=settings.AMOCRM_CHAT_CHANNEL_ID,
                channel_secret=settings.AMOCRM_CHAT_SECRET,
            )
            asyncio.create_task(chat_client.send_message_to_amocrm(
                user_id=sender.id, chat_id=chat_id, text=message_text,
                sender_name=sender_name, phone=getattr(sender, 'phone', None),
            ))
        asyncio.create_task(run_autonomous_advice(chat_id, sender_name, message_text))
    except Exception as log_ex:
        logger.error(f"[USERBOT] Failed to log incoming message: {log_ex}")


async def _handle_media_and_voice(event: Any, sender: Any, sender_name: str) -> None:
    client = getattr(app_ctx, "client", None)
    voice_processor = getattr(app_ctx, "voice_processor", None)
    admin_bot = getattr(app_ctx, "admin_bot", None)
    surgical_integration = getattr(app_ctx, "surgical_integration", None)
    auto_reply_gate = getattr(app_ctx, "auto_reply_gate", None)

    if event.is_private and not event.out and event.message.voice and voice_processor:
        from src.handlers.message_handler import process_voice
        await process_voice(
            event, client=client, sender=sender, sender_name=sender_name,
            msg_controller=app_ctx.msg_controller, voice_processor=voice_processor,
            admin_bot=admin_bot, surgical_integration=surgical_integration,
            auto_reply_gate=auto_reply_gate,
        )
    if event.is_private and not event.out and (event.message.photo or event.message.document):
        from src.handlers.message_handler import process_media
        await process_media(
            event, client=client, sender_name=sender_name,
            msg_controller=app_ctx.msg_controller, admin_bot=admin_bot,
            voice_processor=voice_processor,
        )


async def handle_new_message(event):
    """Barcha kiruvchi xabarlarni xavfsizlik va aqllilik bilan tahlil qilish."""
    from src.handlers.message_handler import (
        advance_checkpoint,
        process_admin_commands,
        process_hisobchi,
        process_elite_intake,
        process_ai_reply,
    )
    from src.entrypoint.crm_push import sync_single_lead

    client = getattr(app_ctx, "client", None)
    bot_client = getattr(app_ctx, "bot_client", None)
    safe_responder = getattr(app_ctx, "safe_responder", None)
    voice_processor = getattr(app_ctx, "voice_processor", None)
    auto_lead_agent = getattr(app_ctx, "auto_lead_agent", None)
    folder_manager = getattr(app_ctx, "folder_manager", None)
    admin_bot = getattr(app_ctx, "admin_bot", None)
    auto_reply_gate = getattr(app_ctx, "auto_reply_gate", None)
    surgical_integration = getattr(app_ctx, "surgical_integration", None)
    action_parser = getattr(app_ctx, "action_parser", None)

    tn5_group_id = getattr(settings, "TN5_GROUP_ID", None)
    tn5_topic_id = getattr(settings, "TN5_TOPIC_ID", None)

    if client and safe_responder:
        me = await client.get_me()
        await safe_responder.update_me_id(me.id)

    sender, sender_name, msg_text = await _broadcast_incoming_message(event)
    await advance_checkpoint(event, app_ctx.msg_controller)

    if _should_block_private_userbot_reply(event) or (safe_responder and not await safe_responder.should_respond(event)):
        return

    if tn5_group_id and event.chat_id == tn5_group_id and getattr(event.message.reply_to, "reply_to_msg_id", None) == tn5_topic_id:
        asyncio.create_task(sync_single_lead(event))
        return

    if await process_admin_commands(
        event,
        client=client,
        bot_client=bot_client,
        msg_controller=app_ctx.msg_controller,
        settings=settings,
        meeting_scheduler=getattr(app_ctx, "meeting_scheduler", None),
        get_surgical_integration=getattr(app_ctx, "get_surgical_integration", None),
        _negotiation_int=_negotiation_int,
        lead_scraper=getattr(app_ctx, "lead_scraper", None),
        audit_agent=getattr(app_ctx, "audit_agent", None),
        auto_lead_agent=auto_lead_agent,
        admin_bot=admin_bot,
        TN5_GROUP_ID=tn5_group_id,
        TN5_TOPIC_ID=tn5_topic_id,
    ):
        return

    message_text = event.message.message or ""
    chat_id = event.chat_id
    if await process_hisobchi(
        event,
        client=client,
        sender=sender,
        message_text=message_text,
        msg_controller=app_ctx.msg_controller,
        voice_processor=voice_processor,
        settings=settings,
    ):
        return

    await _sync_and_log_crm_channels(event, sender, sender_name, message_text, chat_id)

    personal = await _is_personal_folder_sender(sender)
    if not personal and event.is_private and not event.out and not getattr(sender, "bot", False):
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
            TN5_GROUP_ID=tn5_group_id,
        )

    await _handle_media_and_voice(event, sender, sender_name)
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


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


async def self_command_handler(event):
    """Handle commands from the owner in 'Saved Messages'."""
    if not event.message.text:
        return
    from src.handlers.msg_pipeline.admin_commands import process_admin_commands
    await process_admin_commands(
        event,
        client=getattr(app_ctx, "client", None),
        bot_client=getattr(app_ctx, "bot_client", None),
        msg_controller=getattr(app_ctx, "msg_controller", None),
        settings=settings,
        meeting_scheduler=getattr(app_ctx, "meeting_scheduler", None),
        get_surgical_integration=getattr(app_ctx, "get_surgical_integration", None),
        _negotiation_int=getattr(app_ctx, "_negotiation_int", None),
        lead_scraper=getattr(app_ctx, "lead_scraper", None),
        audit_agent=getattr(app_ctx, "audit_agent", None),
        auto_lead_agent=getattr(app_ctx, "auto_lead_agent", None),
        admin_bot=getattr(app_ctx, "admin_bot", None),
        TN5_GROUP_ID=getattr(settings, "TN5_GROUP_ID", None),
        TN5_TOPIC_ID=getattr(settings, "TN5_TOPIC_ID", None),
    )
