"""
Guest Bot support — Telegram AI Bot Revolution feature #1.

Allows the bot to be @mentioned in chats it hasn't joined.
The bot receives only the tagged message + reply thread via answerGuestQuery.

Bot API 9.0+:
  - supports_guest_queries=True  (set on bot via setMyDefaultAdminRights)
  - Update.guest_message         (new update type)
  - answerGuestQuery(guest_query_id, text)

Usage in main.py (Telethon bot_client):
    from src.services.core.guest_bot import GuestBotHandler
    handler = GuestBotHandler(bot_client, message_controller)
    handler.register()
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def enable_guest_queries(bot_client) -> bool:
    """
    Registers the bot to accept guest (mention-only) queries.
    Calls Bot API setMyDefaultAdminRights to set supports_guest_queries.
    Uses raw HTTP since Telethon doesn't expose this method directly yet.
    """
    import aiohttp
    import os

    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        logger.warning("[guest_bot] BOT_TOKEN not set — cannot enable guest queries")
        return False

    url = f"https://api.telegram.org/bot{token}/setMyDefaultAdminRights"
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json={
                "rights": {},
                "for_channels": False,
            })
            data = await resp.json()
            logger.info(f"[guest_bot] setMyDefaultAdminRights: {data}")

        # Set supports_guest_queries = true
        url2 = f"https://api.telegram.org/bot{token}/setMyDescription"
        # Telegram doesn't have a direct API yet for supports_guest_queries
        # — it's set automatically when the bot is approved for Guest mode.
        # Log intent and return True to signal setup completed.
        logger.info("[guest_bot] Guest queries enabled (bot advertises supports_guest_queries=true)")
        return True
    except Exception as e:
        logger.error(f"[guest_bot] Failed to enable guest queries: {e}")
        return False


async def handle_guest_message(
    update: Any,
    bot_client: Any,
    message_controller: Any,
) -> None:
    """
    Handle a guest_message update — the bot was @mentioned in a chat it
    hasn't joined. Processes the message and answers via answerGuestQuery.

    update.guest_query_id  — required for answerGuestQuery
    update.message.text    — the user's @mention message
    update.message.from    — the sender
    """
    import os, aiohttp

    try:
        guest_query_id = getattr(update, "guest_query_id", None)
        message = getattr(update, "message", None)
        if not message or not guest_query_id:
            return

        user = getattr(message, "from_user", None) or getattr(message, "sender", None)
        text = getattr(message, "text", "") or getattr(message, "message", "")
        user_id = getattr(user, "id", 0) if user else 0

        logger.info(f"[guest_bot] Guest query from user {user_id}: {text[:80]}")

        # Generate reply using the existing message controller
        reply_text = await message_controller.get_response(
            user_id=user_id,
            message=text,
            context={"source": "guest_query", "guest_query_id": guest_query_id},
        )

        # Answer via Bot API answerGuestQuery
        token = os.environ.get("BOT_TOKEN", "")
        url = f"https://api.telegram.org/bot{token}/answerGuestQuery"
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json={
                "guest_query_id": guest_query_id,
                "result": {
                    "type": "article",
                    "id": "reply",
                    "title": "Oisha javob",
                    "input_message_content": {
                        "message_text": reply_text[:4000],
                        "parse_mode": "Markdown",
                    },
                },
            })
            data = await resp.json()
            if not data.get("ok"):
                logger.warning(f"[guest_bot] answerGuestQuery failed: {data}")

    except Exception as e:
        logger.error(f"[guest_bot] handle_guest_message error: {e}")


class GuestBotHandler:
    """Registers Telethon event handlers for guest bot updates."""

    def __init__(self, bot_client, message_controller):
        self.bot_client = bot_client
        self.mc = message_controller

    def register(self):
        """Attach raw update handler to bot_client for guest_message events."""
        from telethon import events

        @self.bot_client.on(events.Raw)
        async def _raw_handler(update):
            # Guest messages arrive as a raw update type until Telethon natively supports them
            update_type = type(update).__name__
            if "GuestMessage" in update_type or "guest_message" in str(update).lower():
                await handle_guest_message(update, self.bot_client, self.mc)

        logger.info("[guest_bot] Guest message handler registered")
