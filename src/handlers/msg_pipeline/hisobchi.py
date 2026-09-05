from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from telethon import TelegramClient

from src.services.core.finance.handlers import (
    handle_card_bot_message,
    handle_finance_group_reply,
    is_card_bot_sender,
)

logger = logging.getLogger("OishaHisobchiHandler")

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
    """Hisobchi AI — card bot xabarlarini qayta ishlash.
    Qaytaradi: True = xabar qayta ishlandi, False = davom etish.
    """
    try:
        # Show typing indicator while processing Hisobchi messages
        try:
            from telethon.tl.functions.messages import SetTypingRequest
            from telethon.tl.types import SendMessageTypingAction

            await client(SetTypingRequest(event.chat_id, SendMessageTypingAction()))
        except Exception as exc:
            logger.debug("[HISOBCHI] Failed to show typing indicator: %s", exc)

        from src.services.core.finance.hisobchi_engine import HisobchiEngine
        from src.services.core.finance.handlers import _get_finance_config
        from src.context import app_ctx

        # Ignore Saved Messages (chat with self)
        if client:
            me = await client.get_me()
            if event.is_private and event.chat_id == me.id:
                return False

        _hisobchi_engine = app_ctx.hisobchi_engine or HisobchiEngine(msg_controller.db)

        # Card bot messages handling
        if event.is_private and not event.out and is_card_bot_sender(sender):
            await handle_card_bot_message(event, client, _hisobchi_engine, bot_client=app_ctx.bot_client)
            return True

        if not event.out and event.message.voice and voice_processor:
            finance_group_id, _, _ = _get_finance_config()
            is_finance_chat = (finance_group_id is not None and event.chat_id == finance_group_id)
            is_auth_user = False
            if event.is_private:
                managers = getattr(settings, "SALES_MANAGER_IDS", [])
                sender_id = getattr(sender, "id", None)
                me = await client.get_me()
                is_auth_user = (sender_id is not None and (sender_id in managers or sender_id == me.id))
            if is_finance_chat or is_auth_user:
                from src.services.core.finance.handlers import process_finance_voice_message

                was_voice_hisobchi = await process_finance_voice_message(
                    event, client, _hisobchi_engine, voice_processor
                )
                if was_voice_hisobchi:
                    return True

        # Handle manual group logs (text, photos) sent directly in finance group
        finance_group_id, kirim_topic_id, chiqim_topic_id = _get_finance_config()
        is_finance_chat = (finance_group_id is not None and event.chat_id == finance_group_id)

        if is_finance_chat and not event.out:
            # 1. Photos (receipts) posted in finance group topics
            if event.message.photo:
                from src.services.core.finance.handlers import handle_receipt_photo
                reply_to = getattr(event.message, "reply_to", None)
                topic_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None
                direction = "in" if topic_id == kirim_topic_id else "out"
                if await handle_receipt_photo(
                    event, _hisobchi_engine, client=client, voice_processor=voice_processor, direction=direction
                ):
                    return True

            # 2. Text commands or plain text posted in finance group topics
            if message_text:
                from src.services.core.finance.handlers import (
                    handle_kirim_chiqim_text,
                    handle_topic_plain_text,
                )
                # First try command format /?kirim or /?chiqim
                if await handle_kirim_chiqim_text(event, _hisobchi_engine, message_text):
                    return True

                # If sent directly in Kirim/Chiqim topics, support plain text "50000 taxi"
                reply_to = getattr(event.message, "reply_to", None)
                topic_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None
                if topic_id in (kirim_topic_id, chiqim_topic_id):
                    direction = "in" if topic_id == kirim_topic_id else "out"
                    if await handle_topic_plain_text(event, _hisobchi_engine, message_text, direction):
                        return True

        if not event.is_private and not event.out and message_text:
            was_hisobchi = await handle_finance_group_reply(
                event, client, _hisobchi_engine, bot_client=app_ctx.bot_client
            )
            if was_hisobchi:
                return True
    except Exception as exc:
        logger.error("[HISOBCHI] Handler error: %s", exc, exc_info=True)

    return False
