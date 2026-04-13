import os
import sys
import asyncio
import logging

# [CRITICAL] Ensure local modules are discoverable
sys.path.append(os.getcwd())

from telethon import TelegramClient
from src.config import settings
from src.database import Database
from src.services.lead_scraper import LeadScraper
from src.services.amocrm_sync import AmoCRMSync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def trigger_sync():
    db = Database()
    
    crm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    # Use the session file directly in root (no .gemini subfolder)
    session_path = 'oisha_userbot' 
    
    client = TelegramClient(
        session_path,
        settings.API_ID,
        settings.API_HASH
    )
    
    async with client:
        if not await client.is_user_authorized():
            logger.error("Userbot not authorized!")
            return
            
        scraper = LeadScraper(google_service=None, db=db, client=client, amocrm=crm)
        
        # TN5 Group ID
        TN5_CHAT_ID = -1002347167664 
        
        logger.info(f"🚀 Starting immediate TN5 sync for Juma feature...")
        # Sync 5 members just to verify it works and populate a small audience
        await scraper.sync_all_group_members(
            client=client, 
            group_id=TN5_CHAT_ID, 
            limit=5, 
            group_label="TEZ NATIJA 5",
            prefix="TN5"
        )
        logger.info("✅ Initial sync complete. audience is now populated.")

if __name__ == "__main__":
    asyncio.run(trigger_sync())
