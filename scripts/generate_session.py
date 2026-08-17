"""Generate a new Telethon StringSession for Oisha-OS userbot."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import getpass
getpass.getpass = lambda prompt="": input(prompt)

from telethon import TelegramClient
from telethon.sessions import StringSession

try:
    from src.settings import settings
    API_ID = settings.API_ID
    API_HASH = settings.API_HASH
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")

if not API_ID or not API_HASH:
    print("[ERROR] API_ID yoki API_HASH topilmadi!")
    sys.exit(1)

async def main():
    print("=" * 50)
    print("Oisha-OS Yangi Session Yaratish")
    print("=" * 50)
    print()
    
    client = TelegramClient(
        StringSession(), API_ID, API_HASH,
        device_model="Oisha Enterprise v2",
        system_version="Linux Server",
    )
    
    await client.start()
    
    session_string = client.session.save()
    
    print()
    print("=" * 50)
    print("YANGI SESSION STRING:")
    print("=" * 50)
    print()
    print(session_string)
    print()
    print("=" * 50)
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
