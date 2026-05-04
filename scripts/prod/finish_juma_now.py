import asyncio
import os
import sys
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Ensure we can import src
sys.path.append(os.getcwd())

from src.database import Database
from src.services.core.juma_notifier import JumaNotifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("JumaFinisher")

async def main():
    load_dotenv()
    
    session_string = os.getenv("USERBOT_SESSION_STRING")
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    
    if not all([session_string, api_id, api_hash]):
        logger.error("Missing credentials in .env!")
        return

    db = Database()
    
    # We use StringSession to avoid "session file locked" errors with the cloud bot
    client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
    
    try:
        await client.start()
        if not await client.is_user_authorized():
            logger.error("Userbot not authorized!")
            return
            
        logger.info("🚀 Juma Finisher started. Checking remaining classmates...")
        notifier = JumaNotifier(client=client, db=db)
        
        # This will send greetings to everyone in data/juma_outreach_list.csv who hasn't received it yet today.
        # It has built-in delays to prevent spam bans.
        await notifier.check_and_send()
        
        logger.info("✅ Juma outreach cycle completed successfully.")
    except Exception as e:
        logger.error(f"❌ Error during outreach: {e}")
    finally:
        await client.disconnect()
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
