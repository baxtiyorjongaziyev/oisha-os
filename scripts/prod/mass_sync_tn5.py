
import asyncio
import os
import sys
import logging

# Add the project root to sys.path
project_root = r"c:\Users\baxti\playground\oisha-os"
sys.path.append(project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MASS_SYNC_TN5")

from telethon import TelegramClient
from src.settings import settings
from src.services.lead_scraper import LeadScraper
from src.services.google_service import GoogleService
from src.database import Database
from src.services.amocrm_sync import AmoCRMSync

async def run_sync():
    # 1. Initialize dependencies
    db = Database()
    google = GoogleService()
    
    # Initialize AmoCRM
    amo = None
    try:
        amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value(),
            redirect_url=settings.AMOCRM_REDIRECT_URL
        )
    except Exception as e:
        logger.error(f"AmoCRM Init Error: {e}")

    # 2. Setup Telegram Client
    session_path = os.path.join(project_root, 'data', 'userbot_session')
    client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Client not authorized. Please run authorization script first.")
            return

        # 3. Initialize Scraper
        scraper = LeadScraper(google_service=google, db=db, client=client, amocrm=amo)
        
        # 4. Run Mass Sync
        target_group_id = -1002242445831
        logger.info(f"Starting FULL mass sync for group {target_group_id} (No phone numbers skip: True)...")
        
        synced = await scraper.sync_all_group_members(client, target_group_id, limit=500, no_phone_only=True) 
        
        # 5. Verification: Check Account Contact List
        from telethon import functions
        contacts = await client(functions.contacts.GetContactsRequest(hash=0))
        total_contacts = len(contacts.users)
        
        logger.info(f"Verification: Total contacts in your account: {total_contacts}")
        logger.info(f"Mass sync finished. Total synced in this batch: {synced}")

    except Exception as e:
        logger.error(f"Execution Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_sync())
