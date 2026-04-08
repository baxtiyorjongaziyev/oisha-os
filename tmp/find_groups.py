
import asyncio
import os
import sys
from telethon import TelegramClient

# App root-ga o'tish
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.settings import settings

async def find_tez_natija_groups():
    client = TelegramClient(os.path.join("data", "discovery_session"), settings.API_ID, settings.API_HASH)
    await client.connect()
    
    print("🔍 'Tez Natija' guruhlarini qidirish...")
    async for dialog in client.iter_dialogs():
        if "TEZ NATIJA" in dialog.name.upper():
            print(f"✅ Topildi: '{dialog.name}' | ID: {dialog.id}")
            
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(find_tez_natija_groups())
