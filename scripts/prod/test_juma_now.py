import asyncio
import os
import sys
import logging
from datetime import datetime

# [CRITICAL] Ensure local modules are discoverable
sys.path.append(os.getcwd())

from telethon import TelegramClient
from src.config import settings
from src.database import Database
from src.services.juma_notifier import JumaNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_juma_immediately():
    db = Database()
    
    # Use the authorized session discovered: data/bot_session
    session_path = 'data/bot_session' 
    
    client = TelegramClient(
        session_path,
        settings.API_ID,
        settings.API_HASH
    )
    
    async with client:
        if not await client.is_user_authorized():
            logger.error("Userbot not authorized! Please log in first.")
            return
            
        notifier = JumaNotifier(client=client, db=db)
        
        # 1. TEST GREETING (Directly to Owner for safety)
        owner_id = int(settings.OWNER_ID)
        logger.info(f"👸 [TEST] Sending Juma greeting to Owner ({owner_id})...")
        
        # Mocking the templates for the test
        message = "👸 [TEST MODE] Assalomu alaykum! Jumaning xayru barokati sizga bo'lsin! 🕌✨ 👸🛡️"
        
        try:
            await client.send_message(owner_id, message)
            logger.info("✅ SUCCESS: Test greeting sent to your Telegram!")
            print("\n✅ TABRIKLAYMAN! Test xabari Telegramingizga yuborildi. Tekshirib ko'ring!")
        except Exception as e:
            logger.error(f"❌ TEST FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_juma_immediately())
