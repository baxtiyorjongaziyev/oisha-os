
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
        for l in leads[:5]:
            print(f"✅ Lid: {l['name']} | Summa: {l['price']} UZS | ID: {l['id']}")
    except Exception as e:
        print(f"❌ AmoCRM Error: {e}")

    # 2. Google Contacts
    print("\n--- GOOGLE CONTACTS (YANGI KONTAKTLAR) ---")
    try:
        google = GoogleService()
        contacts = await google.list_contacts(10)
        for c in contacts[:5]:
            name = c.get('names', [{}])[0].get('displayName', 'No name')
            phones = [p.get('value') for p in c.get('phoneNumbers', [])]
            print(f"✅ Kontakt: {name} | Tel: {', '.join(phones)}")
    except Exception as e:
        print(f"❌ Google Error: {e}")

    # 3. Telegram (Oxirgi yuborilgan xabarlar)
    print("\n--- TELEGRAM (JON BRANDING TEAM GURUHI) ---")
    try:
        async with TelegramClient('research_session', settings.API_ID, settings.API_HASH) as client:
            entity = await client.get_entity(settings.CRM_GROUP_ID)
            messages = await client.get_messages(entity, limit=5)
            for m in messages:
                if m.sender_id == (await client.get_me()).id:
                    text = (m.text or m.message or "")[:50].replace("\n", " ")
                    print(f"✅ Bot xabari: {text}...")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_proof())
