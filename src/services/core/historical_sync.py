import asyncio
import logging
import datetime
import random
from typing import List, Optional
from telethon import TelegramClient, functions, errors
from src.database import Database
from src.services.core.auto_lead_agent import AutoLeadAgent
from src.settings import settings

logger = logging.getLogger("HistoricalSync")

class HistoricalSyncService:
    def __init__(self, db: Database, client: TelegramClient):
        self.db = db
        self.client = client
        self.auto_lead_agent = AutoLeadAgent(api_key=settings.GEMINI_API_KEY.get_secret_value())
        self.is_running = False

    async def start_backlog_sync(self, days: int = 365, limit_dialogs: int = 500):
        """1 yillik tarixni skanerlashni boshlash."""
        if self.is_running:
            logger.warning("Historical sync is already running!")
            return
        
        self.is_running = True
        logger.info(f"🚀 [HISTORICAL] Starting sync for {days} days history...")

        try:
            sync_start_time = datetime.datetime.now() - datetime.timedelta(days=days)
            dialog_count = 0
            
            async for dialog in self.client.iter_dialogs(limit=limit_dialogs):
                if not dialog.is_user or dialog.entity.bot:
                    continue
                
                # Check status
                status = await self.db.get_sync_status(str(dialog.id))
                if status == "completed":
                    continue

                logger.info(f"🔍 [HISTORICAL] Syncing chat: {dialog.name} ({dialog.id})")
                await self._sync_chat_history(dialog, sync_start_time)
                
                dialog_count += 1
                # Mark as completed
                await self.db.set_sync_status(str(dialog.id), "completed")
                
                # Safety break
                await asyncio.sleep(random.uniform(2, 5))

            logger.info(f"✅ [HISTORICAL] Sync finished. Processed {dialog_count} dialogs.")
        except Exception as e:
            logger.error(f"❌ [HISTORICAL ERROR] Global sync failure: {e}")
        finally:
            self.is_running = False

    async def _sync_chat_history(self, dialog, start_date):
        """Bitta chatning tarixini yuklash va tahlil qilish."""
        messages_to_log = []
        full_chat_text = []

        try:
            async for msg in self.client.iter_messages(dialog.id, offset_date=None):
                # Stop if message is older than start_date
                if msg.date.replace(tzinfo=None) < start_date:
                    break
                
                if msg.text:
                    role = "AI" if msg.out else "User"
                    text = msg.text
                    messages_to_log.append((dialog.id, text, msg.out, msg.date.isoformat()))
                    full_chat_text.append(f"{role}: {text}")

                # Batch commit every 100 messages
                if len(messages_to_log) >= 100:
                    await self.db.log_messages_batch(messages_to_log)
                    messages_to_log = []
                
                # Telegram limit prevention
                if len(full_chat_text) % 50 == 0:
                    await asyncio.sleep(0.5)

            # Final commit
            if messages_to_log:
                await self.db.log_messages_batch(messages_to_log)

            # --- DEEP INTELLIGENCE ANALYSIS ---
            if full_chat_text:
                # Build context (max 50 messages for AI analysis to save tokens)
                recent_context = "\n".join(full_chat_text[:50])
                logger.info(f"🧠 [DEEP INTEL] Analyzing chat profile for {dialog.name}...")
                
                # Reuse run_autonomous_advice logic or similar
                from src.main import run_autonomous_advice
                # We trigger it as a task to not block the sync
                asyncio.create_task(run_autonomous_advice(dialog.id, dialog.name, "HISTORY_SYNC_TRIGGER"))

        except errors.FloodWaitError as e:
            logger.warning(f"⏳ [FLOOD] Waiting for {e.seconds} seconds due to Telegram limits.")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"❌ [HISTORICAL ERROR] Chat sync failed for {dialog.id}: {e}")

if __name__ == "__main__":
    # Test stub
    pass
