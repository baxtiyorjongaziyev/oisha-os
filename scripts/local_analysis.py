import asyncio
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telethon import TelegramClient
from src.settings import settings

api_id = settings.API_ID
api_hash = settings.API_HASH.get_secret_value() if hasattr(settings.API_HASH, "get_secret_value") else settings.API_HASH

phone = os.environ.get("TELEGRAM_PHONE", "+998336450097")
password = os.environ.get("TELEGRAM_PASSWORD", "")

async def main():
    print("Telethon sessiyasi boshlanmoqda... (Kod kutilmoqda)")
    client = TelegramClient("data/local_temp_session", api_id, api_hash)
    
    # client.start will prompt for code via stdin
    await client.start(
        phone=lambda: phone,
        password=lambda: password
    )
    
    print("Muvaffaqiyatli ulandi! Tahlil boshlanmoqda...")
    dialogs = await client.get_dialogs(limit=30)
    
    users = []
    for d in dialogs:
        if d.is_user and not d.entity.bot:
            users.append(f"- {d.name} (ID: {d.id})")
            
    print(f"Topilgan shaxsiy chatlar ({len(users)} ta):")
    for u in users:
        print(u)
        
    print("\nTahlil yakunlandi.")
    
if __name__ == "__main__":
    asyncio.run(main())
