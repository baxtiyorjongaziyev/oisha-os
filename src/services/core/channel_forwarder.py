import asyncio
import logging
import random
from datetime import datetime
from telethon import TelegramClient, events
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ChannelForwarder:
    """
    Monitors a specific channel and performs conditional forwarding.
    - Friday Juma Greetings -> All TN Classmates (DM)
    - Trigger #forward -> Business Groups
    """

    def __init__(self, client: TelegramClient, db, monitor_channel: str, juma_notifier=None):
        self.client = client
        self.db = db
        self.monitor_channel = monitor_channel
        self.juma_notifier = juma_notifier
        self.is_running = False

    async def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        logger.info(f"👸 [FORWARDER] Smart monitoring active for: {self.monitor_channel}")

        @self.client.on(events.NewMessage(chats=self.monitor_channel))
        async def handler(event):
            if not event.message or not event.message.text:
                return
            
            text = event.message.text
            now = datetime.now()
            
            # 1. JUMA LOGIC (Friday only, AI checked)
            if now.weekday() == 4 and self.juma_notifier:
                is_juma = await self.juma_notifier.is_juma_greeting(text)
                if is_juma:
                    logger.info(f"👸 [FORWARDER] Juma greeting detected! Forwarding to all classmates...")
                    asyncio.create_task(self.juma_notifier.send_greetings(now.strftime('%Y-%m-%d'), source_message=event.message))
                    return

            # 2. TRIGGER LOGIC (#forward)
            if "#forward" in text.lower():
                logger.info(f"👸 [FORWARDER] Trigger #forward detected! Forwarding to business groups...")
                asyncio.create_task(self.forward_to_business_groups(event.message))

    async def forward_to_business_groups(self, message):
        """Forward a message to groups related to entrepreneurs/business."""
        try:
            # Discover groups with "Tadbirkor" or from a specific list
            targets = []
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    title = dialog.name.lower()
                    if "tadbirkor" in title or "biznes" in title or "tn5" in title:
                        targets.append(dialog.id)
            
            if not targets:
                logger.warning("👸 [FORWARDER] No business groups found for forwarding.")
                return

            logger.info(f"👸 [FORWARDER] Forwarding to {len(targets)} business groups...")
            
            # Clean message text from the trigger tag if needed
            # For forward_messages, we can't easily edit the text, so we just forward.
            
            for g_id in targets:
                try:
                    await self.client.forward_messages(g_id, message)
                    logger.info(f"✅ [FORWARDER] Forwarded to group {g_id}")
                    await asyncio.sleep(random.uniform(30, 60)) # Faster for groups than DMs
                except Exception as e:
                    logger.error(f"❌ [FORWARDER] Group forward error ({g_id}): {e}")
                    
        except Exception as ex:
            logger.error(f"👸 [FORWARDER] Business forward error: {ex}")
