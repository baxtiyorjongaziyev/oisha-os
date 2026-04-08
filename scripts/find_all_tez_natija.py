
import asyncio
import os
import sys
from telethon import TelegramClient

# Add project root to path
sys.path.append(os.getcwd())
from src.settings import settings

async def find_all_tez_natija():
    # Use a separate session to avoid lock
    session_path = os.path.join("data", "discovery_session")
    client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("AUTH_REQUIRED: Please authorize this session in follow-up.")
            return

        print("🔍 Scanning dialogs for TEZ NATIJA groups...")
        async for dialog in client.iter_dialogs():
            if "TEZ NATIJA" in dialog.name.upper():
                print(f"FOUND: {dialog.name} | ID: {dialog.id}")
                
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(find_all_tez_natija())
