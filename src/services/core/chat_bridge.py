import logging
import asyncio
import os
from telethon import TelegramClient, events, types
from src.settings import settings

logger = logging.getLogger("ChatBridge")

class ChatBridge:
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient, db):
        self.user_client = user_client
        self.bot_client = bot_client
        self.db = db
        self.team_group_id = settings.CRM_GROUP_ID
        self.owner_id = settings.OWNER_ID

    async def setup_handlers(self):
        """
        [GOD MODE] Intercepts personal DMs and bridges them to the team.
        """
        # 1. Listen for Incoming DMs on the User (Personal) account
        @self.user_client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def incoming_dm_handler(event):
            sender = await event.get_sender()
            if not sender or event.sender_id == self.owner_id:
                return

            # Check if this is a business message (Simple AI filter placeholder)
            text = event.raw_text or ""
            # Forward to team group via Bot
            forward_msg = (
                f"📥 **YANGI XABAR (SHAXSIYDAN)**\n\n"
                f"👤 Mijoz: {getattr(sender, 'first_name', 'Mijoz')} (@{getattr(sender, 'username', 'yoq')})\n"
                f"🆔 ID: `{event.sender_id}`\n"
                f"📝 Xabar: {text}\n\n"
                f"💬 Javob berish uchun shu xabarga **Reply** qiling."
            )
            
            # Store the mapping to know who to reply to
            await self.db.set_state(f"bridge_map_{event.id}", event.sender_id)
            await self.bot_client.send_message(self.team_group_id, forward_msg)
            logger.info(f"👸 [BRIDGE] Forwarded message from {event.sender_id} to team.")

        # 2. Listen for Team Replies in the Group
        @self.bot_client.on(events.NewMessage(chats=self.team_group_id))
        async def team_reply_handler(event):
            if not event.is_reply:
                return

            # Get the original bridge message
            reply_to = await event.get_reply_message()
            target_user_id = await self.db.get_state(f"bridge_map_{reply_to.id}")
            
            if target_user_id:
                # Send the team's reply to the customer via YOUR (userbot) account
                try:
                    await self.user_client.send_message(int(target_user_id), event.raw_text)
                    await event.reply("✅ Xabaringiz mijozga shaxsiy Telegramdan yuborildi.")
                    logger.info(f"👸 [BRIDGE] Sent team reply to {target_user_id} via userbot.")
                except Exception as e:
                    logger.error(f"👸 [BRIDGE ERROR] Failed to send reply: {e}")

    async def close(self):
        pass # No session to close in this implementation
