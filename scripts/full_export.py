#!/usr/bin/env python3
"""
👸 OISHA: Tez Natija 4 - To'liq Avtorizatsiya va Contact Saqlash

Bu script avtomatik:
1. Telegram userbot avtorizatsiyasi (agar kerak bo'lsa)
2. Google Contacts avtorizatsiyasi
3. Tez Natija 4 guruhidan barcha contactlarni yig'ish
4. Google Contacts-ga saqlash

Ishga tushirish: .venv_oi\\Scripts\\python scripts\\full_export.py
"""

import asyncio
import logging
import os
import random
import sys
import pickle
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from src.settings import settings
from src.database import Database

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OishaFullExport")

# Constants
SESSION_NAME = 'oisha_userbot'
TOKEN_FILE = 'token.pickle'
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/contacts']


class GoogleContactsAuth:
    """Google Contacts avtorizatsiyasi uchun helper."""
    
    def __init__(self):
        self.service = None
        self.creds = None
        
    def authenticate(self):
        """OAuth2 orqali avtorizatsiya."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                self.creds = pickle.load(token)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                print("\n" + "="*60)
                print("📱 GOOGLE AVTORIZATSIYA")
                print("="*60)
                print("Google Contacts uchun ruxsat so'ralmoqda...")
                print("Brauzer ochiladi, iltimos ruxsat bering!")
                print("="*60 + "\n")
                
                # Create credentials.json from environment if exists
                creds_data = getattr(settings, 'GOOGLE_CREDENTIALS_JSON', None)
                if creds_data:
                    with open('credentials.json', 'w') as f:
                        json.dump(creds_data, f)
                
                if not os.path.exists('credentials.json'):
                    print("❌ credentials.json fayli topilmadi!")
                    print("Google Cloud Console dan yuklab oling:")
                    print("https://console.cloud.google.com/apis/credentials")
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(self.creds, token)
        
        self.service = build('people', 'v1', credentials=self.creds)
        print("✅ Google Contacts avtorizatsiyasi muvaffaqiyatli!")
        return True
    
    def create_contact(self, first_name, last_name="", phones=None, note="", group_name=None):
        """Yangi kontakt yaratish."""
        if not self.service:
            return False
        
        try:
            phone_entries = []
            if phones:
                if isinstance(phones, str):
                    phones = [phones]
                for i, p in enumerate(phones):
                    phone_entries.append({"value": p, "type": "mobile" if i == 0 else "work"})
            
            contact_body = {
                "names": [{"givenName": first_name, "familyName": last_name}],
                "phoneNumbers": phone_entries,
                "biographies": [{"value": note, "contentType": "TEXT_PLAIN"}] if note else []
            }
            
            result = self.service.people().createContact(body=contact_body).execute()
            logger.info(f"✅ Google Contacts: {first_name} {last_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Google Contacts xato: {e}")
            return False


async def telegram_auth():
    """Telegram userbot avtorizatsiyasi."""
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    try:
        await client.connect()
        if await client.is_user_authorized():
            print("✅ Telegram userbot allaqachon avtorizatsiya qilingan!")
            await client.disconnect()
            return True
        await client.disconnect()
    except Exception as e:
        logger.warning(f"Telegram tekshiruv xato: {e}")
    
    print("\n" + "="*60)
    print("📱 TELEGRAM AVTORIZATSIYA")
    print("="*60)
    print("Telefon raqamingizni kiriting (masalan: +998901234567)")
    print("="*60 + "\n")
    
    # Interactive auth - Telethon handles this
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    await client.start()
    
    if await client.is_user_authorized():
        print("✅ Telegram avtorizatsiyasi muvaffaqiyatli!")
        await client.disconnect()
        return True
    
    await client.disconnect()
    return False


async def export_contacts():
    """Asosiy export funksiyasi."""
    
    # 1. TELEGRAM AVTORIZATSIYA
    print("\n🔐 TELEGRAM TEKSHIRUV...")
    telegram_ready = False
    try:
        client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
        await client.connect()
        telegram_ready = await client.is_user_authorized()
        await client.disconnect()
    except:
        pass
    
    if not telegram_ready:
        print("❌ Telegram avtorizatsiyasi kerak!")
        print("Iltimos, quyidagi buyruqni alohida terminalda ishga tushiring:")
        print("\n   .venv_oi\\Scripts\\python -c \"import asyncio; from telethon import TelegramClient; from src.settings import settings; c = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH); asyncio.run(c.start())\"\n")
        print("Telefon raqam va kodni kiritib, qayta urining.")
        return
    
    # 2. GOOGLE AVTORIZATSIYA
    print("\n🔐 GOOGLE CONTACTS TEKSHIRUV...")
    gcontacts = GoogleContactsAuth()
    if not os.path.exists(TOKEN_FILE):
        print("❌ Google Contacts avtorizatsiyasi kerak!")
        print("Iltimos, quyidagi buyruqni ishga tushiring (brauzer ochiladi):")
        print("\n   .venv_oi\\Scripts\\python scripts\\google_auth.py\n")
        return
    
    if not gcontacts.authenticate():
        print("❌ Google Contacts ulanmadi!")
        return
    
    # 3. CONTACTLARNI YIG'ISH VA SAQLASH
    print("\n" + "="*60)
    print("🚀 CONTACT EXPORT BOSHLANDI")
    print("="*60)
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    saved_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        await client.connect()
        
        # Guruhni qidirish
        print(f"\n🔍 'Tez Natija 4' guruhi qidirilmoqda...")
        target_group = None
        
        async for dialog in client.iter_dialogs():
            if "tez natija 4" in dialog.name.lower():
                target_group = dialog
                print(f"✅ Topildi: {dialog.name} (ID: {dialog.id})")
                break
        
        if not target_group:
            print("❌ Guruh topilmadi! 'Tez Natija 4' nomli guruh bormi?")
            await client.disconnect()
            return
        
        print(f"\n📊 Statistika:")
        print(f"   Guruh: {target_group.name}")
        print(f"   Bu jarayon bir necha daqiqa davom etishi mumkin...")
        print("-" * 60)
        
        # A'zolarni yig'ish
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
            
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or "NoName"
            last_name = user.last_name or ""
            phone = user.phone
            
            # Bazaga saqlash
            db.upsert_user(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                phone=phone,
                role="Lead (TezNatija4)",
                last_seen=None
            )
            
            # Google Contacts-ga saqlash
            if phone:
                note = f"📱 Telegram: @{username if username else 'yoq'}\n🆔 ID: {user_id}\n📂 Guruh: Tez Natija 4"
                
                success = gcontacts.create_contact(
                    first_name=first_name,
                    last_name=last_name or "TN4",
                    phones=[phone],
                    note=note
                )
                
                if success:
                    saved_count += 1
                    print(f"✅ {first_name} {last_name} - {phone}")
                else:
                    error_count += 1
                    print(f"❌ {first_name} - xato")
            else:
                skipped_count += 1
                print(f"⏭️ {first_name} (telefon yo'q)")
            
            # FloodWait oldini olish
            await asyncio.sleep(random.uniform(1.5, 2.5))
        
        # Yakuniy natija
        print("\n" + "="*60)
        print("✅ TUGADI!")
        print("="*60)
        print(f"📇 Google Contacts: {saved_count} ta saqlandi")
        print(f"⏭️ O'tkazildi: {skipped_count} ta (telefon yo'q)")
        print(f"❌ Xatolar: {error_count} ta")
        print("="*60)
        print("📱 Google Contacts ilovasini tekshiring!")
        
    except errors.FloodWaitError as fe:
        print(f"\n⏳ FloodWait: {fe.seconds} soniya kuting va qayta urining.")
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print("👸 OISHA OS - Tez Natija 4 Contact Export")
    print("=" * 70)
    print()
    
    asyncio.run(export_contacts())
