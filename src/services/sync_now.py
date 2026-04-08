
import asyncio
import logging
from telethon import TelegramClient
from settings import settings
from database import Database
from amocrm_sync import AmoCRMSync
from services.lead_scraper import LeadScraper
from services.google_service import GoogleService
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # 1. Init
    db = Database()
    client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
    await client.start()
    
    amocrm = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL
    )
    
    google_service = GoogleService()
    
    scraper = LeadScraper(
        google_service=google_service,
        db=db,
        client=client,
        amocrm=amocrm
    )
    
    # 2. Sync
    logger.info("👸 Oisha-OS: Deep Sync boshlandi (Limit: 500)...")
    count = await scraper.sync_private_dialogs(client, limit=500)
    logger.info(f"✅ Deep Sync yakunlandi. Jami {count} ta yangi lid tahrir qilindi.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
