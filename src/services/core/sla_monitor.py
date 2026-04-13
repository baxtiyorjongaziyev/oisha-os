import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SLAMonitor:
    """
    Service to track Telegram chats and identify leads waiting for a reply.
    Escalates if SLA (Service Level Agreement) time is exceeded.
    """
    def __init__(self, client, db, advisor, admin_bot, sla_limit_minutes=10):
        self.client = client
        self.db = db
        self.advisor = advisor
        self.admin_bot = admin_bot
        self.sla_limit_minutes = sla_limit_minutes
        self.escalated_chats = set()

    async def check_all_active_chats(self):
        """Iterates through recent dialogs to find unanswered leads."""
        try:
            # We check the top 30 active dialogs for speed and resource efficiency on e2-micro
            async for dialog in self.client.iter_dialogs(limit=30):
                if not dialog.is_user or dialog.entity.bot:
                    continue
                
                # Check if it's a lead (synced to CRM)
                if not await self.db.is_crm_synced(dialog.id):
                    continue

                # Get the last message
                last_msg = dialog.message
                if not last_msg or last_msg.out:
                    # Last message was from us, or chat is empty. No action needed.
                    continue

                # Calculate wait time
                wait_time = datetime.now() - last_msg.date.replace(tzinfo=None)
                
                if wait_time > timedelta(minutes=self.sla_limit_minutes):
                    if dialog.id not in self.escalated_chats:
                        await self.escalate_lead(dialog, wait_time)
                        self.escalated_chats.add(dialog.id)
                else:
                    # If they replied, remove from escalated set
                    if dialog.id in self.escalated_chats:
                        self.escalated_chats.remove(dialog.id)
                        
        except Exception as e:
            logger.error(f"[SLA MONITOR] Check error: {e}")

    async def escalate_lead(self, dialog, wait_time):
        """Generates a draft package and notifies the admin/manager."""
        customer_name = getattr(dialog.entity, 'first_name', 'Mijoz')
        wait_min = int(wait_time.total_seconds() / 60)
        
        logger.info(f"🚨 [SLA BREACH] {customer_name} waiting for {wait_min}m. Escalating...")
        
        # 1. Prepare context for AI
        messages = []
        async for msg in self.client.iter_messages(dialog.id, limit=5):
            messages.append(f"{'Menejer' if msg.out else 'Mijoz'}: {msg.text}")
        
        history_context = "\n".join(reversed(messages))
        
        # 2. Generate Draft Packet using Advisor
        advice = await self.advisor.analyze_and_advise(
            chat_id=dialog.id,
            message_text=dialog.message.text,
            history_context=history_context,
            sender_name="Menejer"
        )
        
        if advice:
            header = f"🚨 **SLA BUZILDI!**\n👤 Mijoz: **{customer_name}**\n⏳ Kutish vaqti: **{wait_min} daqiqa**\n\n"
            full_report = header + advice
            
            # 3. Notify
            if self.admin_bot:
                await self.admin_bot.notify_lead(full_report)
            else:
                await self.client.send_message('me', full_report)

    async def run_forever(self, interval=300):
        """Monitoring loop (default every 5 mins)."""
        logger.info(f"🛡️ SLAMonitor initialized (Limit: {self.sla_limit_minutes}m)")
        while True:
            await self.check_all_active_chats()
            await asyncio.sleep(interval)
