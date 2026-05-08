import asyncio
import os
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Set up logging to see progress
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SyncTrigger")

# Add project root to path
import sys

sys.path.append(os.getcwd())

from src.database import Database
from src.services.core.historical_sync import HistoricalSyncService

load_dotenv()


async def run_sync():
    print("[TRIGGER] Initializing Historical Sync...")

    db = Database()
    # Note: connect() in Database class is likely sync or handles its own loop
    # Based on previous viewed code, it sets up the connection
    await db.init_instance()

    session = os.getenv("USERBOT_SESSION_STRING")
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ [ERROR] Client is not authorized. Session might be invalid.")
        return

    print("[CONNECTED] Client authorized. Starting service...")
    sync_service = HistoricalSyncService(db, client)

    # Run sync for 365 days
    await sync_service.start_backlog_sync(days=365)

    print("[FINISH] Historical sync completed.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(run_sync())
