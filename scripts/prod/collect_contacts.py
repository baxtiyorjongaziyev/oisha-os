#!/usr/bin/env python3
"""
👸 OISHA: Tez Natija 4 Contactlarni Yig'ish (Step 1)

Bu script avtomatik:
1. Telegramga ulanadi (allaqachon avtorizatsiya qilingan)
2. Tez Natija 4 guruhi a'zolarini yig'adi
3. SQLite bazaga saqlaydi
4. CSV fayl yaratadi (Google Contacts import uchun)
"""

import asyncio
import logging
import os
import random
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors
from src.settings import settings
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CollectContacts")

SESSION_NAME = 'oisha_userbot'


async def collect_tez_natija_4():
    """Tez Natija 4 contactlarini yig'ish va saqlash."""
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    contacts = []
    saved_count = 0
    skipped_count = 0
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name} (@{me.username})")
        print()
        
        # Guruhni qidirish
        print("🔍 'Tez Natija 4' guruhi qidirilmoqda...")
        target_group = None
        
        async for dialog in client.iter_dialogs():
            if "tez natija 4" in dialog.name.lower():
                target_group = dialog
                print(f"✅ Topildi: {dialog.name} (ID: {dialog.id})")
                break
        
        if not target_group:
            print("❌ 'Tez Natija 4' guruhi topilmadi!")
            print("   Guruh nomini tekshiring...")
            return
        
        print()
        print(f"📊 {target_group.name} dan a'zolarni yig'ish...")
        print("-" * 60)
        
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
            
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or "NoName"
            last_name = user.last_name or ""
            phone = user.phone or ""
            
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
            
            # Ro'yxatga qo'shish
            contact = {
                'user_id': user_id,
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'phone': phone,
                'group': 'Tez Natija 4'
            }
            contacts.append(contact)
            
            if phone:
                saved_count += 1
                print(f"✅ {first_name} {last_name} - {phone}")
            else:
                skipped_count += 1
                print(f"⏭️ {first_name} (telefon yo'q)")
            
            # FloodWait oldini olish
            await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # CSV fayl yaratish
        csv_file = 'tez_natija_4_contacts.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['first_name', 'last_name', 'phone', 'username', 'group'])
            writer.writeheader()
            for c in contacts:
                writer.writerow({
                    'first_name': c['first_name'],
                    'last_name': c['last_name'] or 'TN4',
                    'phone': c['phone'],
                    'username': c['username'],
                    'group': c['group']
                })
        
        # Natija
        print()
        print("=" * 60)
        print("✅ TUGADI!")
        print("=" * 60)
        print(f"📇 Telefon raqamli: {saved_count} ta")
        print(f"⏭️ Telefonsiz: {skipped_count} ta")
        print(f"📊 Jami: {len(contacts)} ta")
        print()
        print(f"📁 CSV fayl: {csv_file}")
        print("=" * 60)
        print()
        print("📱 Google Contacts-ga qo'shish uchun:")
        print("   1. https://contacts.google.com ga kiring")
        print("   2. 'Import' tugmasini bosing")
        print(f"   3. {csv_file} faylini tanlang")
        print()
        
    except errors.FloodWaitError as fe:
        print(f"⏳ FloodWait: {fe.seconds} soniya kuting")
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("👸 OISHA: Tez Natija 4 Contact Yig'uv")
    print("=" * 60)
    print()
    
    asyncio.run(collect_tez_natija_4())
