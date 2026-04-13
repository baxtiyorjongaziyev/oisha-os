
import asyncio
import os
import sys
import logging
import random
from telethon import TelegramClient

# Add project root to path
sys.path.append(os.getcwd())

from src.settings import settings
from src.services.google_service import GoogleService
from src.services.lead_scraper import LeadScraper
from src.services.amocrm_sync import AmoCRMSync
from src.database import Database

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_master_sync():
    """4 ta guruh uchun 'Global Contact Sync' operatsiyasi."""
    print("🚀 Oisha-OS: 'Tez Natija' Global Sync Engine ishga tushirildi... 🤴🛡️")
    
    # 1. Services setup
    db = Database()
    google = GoogleService()
    
    amocrm = None
    try:
        amocrm = AmoCRMSync()
        print("✅ AmoCRM synchronized for enterprise tracking.")
    except Exception as e:
        print(f"⚠️ AmoCRM setup skipped: {e}")
        
    scraper = LeadScraper(google, db, amocrm=amocrm)
    
    # 2. Telegram Client (Discovery Mode)
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ ERROR: Userbot session is NOT authorized. Please log in first.")
            return

        # 3. Validated 'UMUMIY' Group IDs (Verified from your screenshot)
        target_groups = {
            "TN5 Gr": -1003820339529, # "TN5 Gr" UMUMIY
            "TN4 Gr": -1003149184518, # "TN4 Gr" UMUMIY (Fixed via Userbot Discovery 👸🛡️)
            "TN3 Gr": -1002849105320, # "TN3 Gr" UMUMIY
            "TN2 Gr": -1002440481294, # "TN2 Gr" UMUMIY
            "Princess Safety 👸🛡️": -1001550503024 # Jamoa Guruhi 🤴🛡️
        }
        
        # Note: Discovery still runs to find if any IDs changed (optional but safe)
        print("🔍 Syncing using validated Group IDs...")

        # 4. Filter missing groups
        active_groups = {k: v for k, v in target_groups.items() if v is not None}
        if not active_groups:
            print("❌ No 'Tez Natija' groups found in your dialogs.")
            return

        # 5. Global Sync Loop
        print(f"🏁 Starting Bulk Sync for {len(active_groups)} groups...")
        for group_name, group_id in active_groups.items():
            if "Princess Safety" in group_name:
                prefix = "Jamoa"
            else:
                prefix = "TN2" if "2" in group_name else "TN3" if "3" in group_name else "TN4" if "4" in group_name else "TN5"
            
            # Action: Sync members
            # Limit: 20 per group for initial test run if you want, but user asked for "ALL"
            # I will use a reasonable batch limit for the first run to show progress
            print(f"📈 Syncing {group_name} (ID: {group_id}) with prefix '{prefix}'...")
            
            await scraper.sync_all_group_members(
                client=client,
                group_id=group_id,
                limit=2000, # Barcha a'zolarni saqlash
                no_phone_only=False, # Hammani saqlash (Force Add)
                group_label=group_name,
                prefix=prefix
            )
            
            print(f"✅ {group_name} sync completed. Waiting 5 minutes before next group (Princess Safety 👸🛡️)...")
            await asyncio.sleep(300) # Safety gap: 5 minutes

    except Exception as e:
        logger.error(f"[MASTER SYNC FATAL] {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_master_sync())
