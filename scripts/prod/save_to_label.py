#!/usr/bin/env python3
"""
👸 OISHA: "TEZ NATIJA 4" Label-ga Contact Saqlash

Google Contacts-dagi mavjud "TEZ NATIJA 4" label-ga kontaktlarni qo'shadi.
"""

import asyncio
import logging
import os
import random
import sys
import pickle

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from src.settings import settings
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SaveToLabel")

SESSION_NAME = 'oisha_userbot'
TARGET_LABEL = 'TEZ NATIJA 4'
SCOPES = ['https://www.googleapis.com/auth/contacts']
TOKEN_FILE = 'token.pickle'


class GoogleContactsSaver:
    """Google Contacts-ga saqlash uchun helper."""
    
    def __init__(self):
        self.service = None
        self.label_resource_name = None
        self.creds = None
        
    def authenticate(self):
        """OAuth2 orqali avtorizatsiya."""
        print("🔐 Google Contacts avtorizatsiyasi...")
        
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                self.creds = pickle.load(token)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
                print("✅ Token yangilandi")
            else:
                print("❌ credentials.json kerak!")
                print("   https://console.cloud.google.com/apis/credentials")
                return False
            
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(self.creds, token)
        
        self.service = build('people', 'v1', credentials=self.creds)
        print("✅ Google Contacts API ulandi")
        
        # Label ni topish
        return self.find_label()
    
    def find_label(self):
        """Mavjud 'TEZ NATIJA 4' label ni topish."""
        try:
            results = self.service.contactGroups().list(pageSize=1000).execute()
            groups = results.get('contactGroups', [])
            
            for group in groups:
                if group.get('name') == TARGET_LABEL:
                    self.label_resource_name = group.get('resourceName')
                    print(f"✅ Label topildi: {TARGET_LABEL} ({self.label_resource_name})")
                    return True
            
            print(f"❌ '{TARGET_LABEL}' label topilmadi!")
            print("   Iltimos, qo'lda yarating: https://contacts.google.com")
            return False
            
        except Exception as e:
            logger.error(f"Label qidirishda xato: {e}")
            return False
    
    def add_contact_to_label(self, first_name, last_name, phone, note=""):
        """Kontaktni labelga qo'shish."""
        if not self.service or not self.label_resource_name:
            return False
        
        try:
            contact_body = {
                "names": [
                    {
                        "givenName": first_name,
                        "familyName": last_name
                    }
                ],
                "phoneNumbers": [{"value": phone, "type": "mobile"}],
                "biographies": [{"value": note, "contentType": "TEXT_PLAIN"}] if note else [],
                "memberships": [
                    {
                        "contactGroupMembership": {
                            "contactGroupResourceName": self.label_resource_name
                        }
                    }
                ]
            }
            
            result = self.service.people().createContact(body=contact_body).execute()
            return True
            
        except Exception as e:
            logger.error(f"Kontakt qo'shishda xato: {e}")
            return False


async def save_to_tez_natija_4():
    """Kontaktlarni Google Contacts 'TEZ NATIJA 4' label-ga saqlash."""
    
    # Google Contacts auth
    gcontacts = GoogleContactsSaver()
    if not gcontacts.authenticate():
        print("\n❌ Google Contacts ulanmadi!")
        return
    
    # Telegram ulanish
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    saved_count = 0
    error_count = 0
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name}")
        print()
        
        # Guruhni qidirish
        print(f'🔍 "TEZ NATIJA 4" guruhini qidirish...')
        target_group = None
        
        async for dialog in client.iter_dialogs():
            dialog_name = dialog.name or ""
            if "tez natija 4" in dialog_name.lower():
                target_group = dialog
                print(f"✅ Guruh topildi: {dialog.name}")
                break
        
        if not target_group:
            print('❌ Guruh topilmadi!')
            return
        
        print()
        print(f"📊 {target_group.name} dan kontaktlar yig'ilmoqda...")
        print("-" * 70)
        
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
            
            first_name = user.first_name or "NoName"
            last_name = user.last_name or ""
            phone = user.phone
            username = user.username or ""
            
            if not phone:
                continue  # Telefon yo'qlarni o'tkazib yuboramiz
            
            # Ism formati: "Ism Familya TN4 Gr"
            if last_name:
                full_last = f"{last_name} TN4 Gr"
            else:
                full_last = "TN4 Gr"
            
            # Note qo'shish
            note = f"@{username}" if username else "Tez Natija 4 a'zosi"
            
            # Google Contacts-ga saqlash
            success = gcontacts.add_contact_to_label(
                first_name=first_name,
                last_name=full_last,
                phone=phone,
                note=note
            )
            
            if success:
                saved_count += 1
                print(f"✅ {first_name} {full_last} - {phone}")
            else:
                error_count += 1
                print(f"❌ {first_name} - xato")
            
            # Delay (FloodWait oldini olish)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # Har 10 ta da statistika
            if saved_count % 10 == 0:
                print(f"   📈 Jarayon: {saved_count} ta saqlandi...")
        
        # Natija
        print()
        print("=" * 70)
        print(f'✅ "{TARGET_LABEL}" LABEL-GA SAQLANDI!')
        print("=" * 70)
        print(f"📇 Saqlangan: {saved_count} ta")
        print(f"❌ Xatolar: {error_count} ta")
        print("=" * 70)
        print()
        print(f"📱 https://contacts.google.com dan '{TARGET_LABEL}' ni ko'ring")
        
    except errors.FloodWaitError as fe:
        print(f"\n⏳ FloodWait: {fe.seconds} soniya kuting va qayta urining.")
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print(f'👸 OISHA: "{TARGET_LABEL}" Label-ga Contact Saqlash')
    print("=" * 70)
    print()
    
    asyncio.run(save_to_tez_natija_4())
