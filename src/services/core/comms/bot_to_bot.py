"""
Bot-to-Bot messaging — Telegram AI Bot Revolution feature #2.

Allows Oisha-OS agents to autonomously send messages to other bots
(e.g., SurgicalNegotiator → SalesCoach scoring bot, or OishaBrain →
AuditAgent bot) without human involvement.

Telegram Bot API 9.0+ allows bots to initiate conversations with
other bots using the standard sendMessage API — no special permission
needed beyond BOTH bots having started a conversation or being in a
shared group.

Usage:
    from src.services.core.bot_to_bot import BotMessenger
    messenger = BotMessenger()
    await messenger.send(target_bot="@salescoach_bot", text="Score call XYZ")
    response = await messenger.request(target_bot="@audit_bot", text="Audit leads")
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BotMessage:
    bot_username: str
    text: str
    reply_text: Optional[str] = None
    success: bool = False
    error: Optional[str] = None


class BotMessenger:
    """
    Sends messages from Oisha-OS to peer bots via Bot API.
    Uses the Telethon userbot to receive replies (bots can now reply to bots).
    """

    def __init__(self, bot_client=None, userbot_client=None):
        self.bot_client = bot_client      # Telethon bot token client
        self.userbot = userbot_client     # Telethon userbot (receives replies)
        self._pending: dict[str, asyncio.Future] = {}

    async def send(self, target_bot: str, text: str) -> BotMessage:
        """Fire-and-forget: send a message to another bot."""
        if not self.userbot:
            logger.warning("[bot2bot] No userbot client — cannot send bot-to-bot")
            return BotMessage(bot_username=target_bot, text=text,
                              success=False, error="no_userbot")
        try:
            await self.userbot.send_message(target_bot, text)
            logger.info(f"[bot2bot] Sent to {target_bot}: {text[:60]}")
            return BotMessage(bot_username=target_bot, text=text, success=True)
        except Exception as e:
            logger.error(f"[bot2bot] send to {target_bot} failed: {e}")
            return BotMessage(bot_username=target_bot, text=text,
                              success=False, error=str(e))

    async def request(
        self,
        target_bot: str,
        text: str,
        timeout: float = 30.0,
    ) -> BotMessage:
        """
        Send a message to another bot and wait for its reply.
        Requires userbot to be listening for incoming messages from target_bot.
        """
        if not self.userbot:
            return BotMessage(bot_username=target_bot, text=text,
                              success=False, error="no_userbot")

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[target_bot] = fut

        try:
            await self.userbot.send_message(target_bot, text)
            reply_text = await asyncio.wait_for(fut, timeout=timeout)
            return BotMessage(
                bot_username=target_bot,
                text=text,
                reply_text=reply_text,
                success=True,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[bot2bot] Timeout waiting for reply from {target_bot}")
            return BotMessage(bot_username=target_bot, text=text,
                              success=False, error="timeout")
        except Exception as e:
            logger.error(f"[bot2bot] request to {target_bot} failed: {e}")
            return BotMessage(bot_username=target_bot, text=text,
                              success=False, error=str(e))
        finally:
            self._pending.pop(target_bot, None)

    def on_incoming_bot_reply(self, sender_username: str, text: str) -> None:
        """
        Called by the main message handler when a message arrives from a bot.
        Resolves pending request() futures.
        """
        fut = self._pending.get(sender_username)
        if fut and not fut.done():
            fut.set_result(text)

    def register_reply_handler(self, client) -> None:
        """
        Registers a Telethon event handler on the userbot to capture
        replies from other bots and resolve pending futures.
        """
        from telethon import events

        @client.on(events.NewMessage(incoming=True))
        async def _bot_reply_handler(event):
            sender = await event.get_sender()
            if sender and getattr(sender, "bot", False):
                username = f"@{sender.username}" if sender.username else str(sender.id)
                self.on_incoming_bot_reply(username, event.raw_text)

        logger.info("[bot2bot] Bot reply handler registered on userbot")


# Convenience pipeline calls used by SurgicalNegotiator and OishaBrain
async def notify_salescoach(text: str, messenger: Optional[BotMessenger] = None) -> bool:
    """Notify SalesCoach bot about a call or lead event."""
    if not messenger:
        return False
    bot = os.environ.get("SALESCOACH_BOT_USERNAME", "@salescoach_score_bot")
    result = await messenger.send(bot, text)
    return result.success


async def request_audit(text: str, messenger: Optional[BotMessenger] = None) -> Optional[str]:
    """Ask the audit bot to run analysis; return reply text."""
    if not messenger:
        return None
    bot = os.environ.get("AUDIT_BOT_USERNAME", "@oisha_audit_bot")
    result = await messenger.request(bot, text, timeout=60.0)
    return result.reply_text if result.success else None
