
import asyncio
import os
import logging
from dotenv import load_dotenv
load_dotenv()

import sys
# Add parent directory to path to import services correctly
root_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(root_dir)

from amocrm_sync import AmoCRMSync
from services.google_service import GoogleService
from settings import settings
from telethon import TelegramClient
from telethon.tl.types import PeerChat, PeerChannel

async def fetch_proof():
    print("🔍 Oisha-OS: ISBOTLARNI YIG'ISH JARAYONI...\n")
    
    # 1. AmoCRM
    print("--- AMOCRM (YANGI LIDLAR) ---")
    try:
        amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value(),
            redirect_url=settings.AMOCRM_REDIRECT_URL
        )
        leads = await amo.get_leads()
        print(f"✅ AmoCRM reachable; sampled leads: {len(leads[:5])}")
    except Exception:
        print("❌ AmoCRM verification failed")

    # 2. Google Contacts
    print("\n--- GOOGLE CONTACTS (YANGI KONTAKTLAR) ---")
    try:
        google = GoogleService()
        contacts = await google.list_contacts(10)
        print(f"✅ Google Contacts reachable; sampled contacts: {len(contacts[:5])}")
    except Exception:
        print("❌ Google Contacts verification failed")

    # 3. Telegram (Oxirgi yuborilgan xabarlar)
    print("\n--- TELEGRAM (JON BRANDING TEAM GURUHI) ---")
    try:
        async with TelegramClient('research_session', settings.API_ID, settings.API_HASH) as client:
            entity = await client.get_entity(settings.CRM_GROUP_ID)
            messages = await client.get_messages(entity, limit=5)
            me = await client.get_me()
            own_count = sum(1 for message in messages if message.sender_id == me.id)
            print(f"✅ Telegram reachable; own sampled messages: {own_count}")
    except Exception:
        print("❌ Telegram verification failed")

if __name__ == "__main__":
    asyncio.run(fetch_proof())
