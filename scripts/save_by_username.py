#!/usr/bin/env python3
"""
👸 OISHA: Username bilan Telegram Contacts-ga Saqlash

Telefon raqami yo'q foydalanuvchilarni username orqali 
Telegram Contacts-ga saqlash (yangi Telegram funksiyasi)
"""

import asyncio
import logging
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors, functions, types
from src.settings import settings
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SaveByUsername")

SESSION_NAME = 'oisha_userbot'
GROUP_NAME = 'Tez Natija 4'


async def save_contacts_by_username():
    """Telefon yo'q foydalanuvchilarni username bilan saqlash."""
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    saved_count = 0
    error_count = 0
    skipped_count = 0
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name}")
        print()
        
        # Guruhni qidirish
        print(f'🔍 "{GROUP_NAME}" guruhini qidirish...')
        target_group = None
        
        async for dialog in client.iter_dialogs():
            if "tez natija 4" in dialog.name.lower():
                target_group = dialog
                print(f"✅ Topildi: {dialog.name}")
                break
        
        if not target_group:
            print('❌ Guruh topilmadi!')
            return
        
        print()
        print(f"📊 Username bilan kontaktlarni saqlash...")
        print("-" * 70)
        
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
            
            first_name = user.first_name or "NoName"
            last_name = user.last_name or ""
            username = user.username
            phone = user.phone
            user_id = user.id
            
            # Telefon borlarni o'tkazib yuboramiz (ular allaqachon CSV ga saqlangan)
            if phone:
                continue
            
            # Username bo'lmasa saqlab bo'lmaydi
            if not username:
                skipped_count += 1
                print(f"⏭️ {first_name} - username yo'q (o'tkazildi)")
                continue
            
            try:
                # User entity olish
                user_entity = await client.get_entity(username)
                
                # Telegram Contacts-ga qo'shish (phone = "+" yoki bo'sh string)
                # Yangi Telegram funksiyasi - username bilan qo'shish
                result = await client(functions.contacts.AddContactRequest(
                    id=user_entity,
                    first_name=first_name,
                    last_name=last_name or f"TN4 Gr",
                    phone="+",  # Bo'sh yoki '+' - Telegram yangi funksiyasi
                    add_phone_privacy_exception=False
                ))
                
                saved_count += 1
                print(f"✅ {first_name} {last_name} (@{username}) - saqlandi")
                
                # Bazaga belgi qo'yish
                db.upsert_user(
                    user_id=user_id,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    phone="SAVED_AS_CONTACT",
                    role="Contact (Username Only)",
                    last_seen=None
                )
                
                # Xavfsizlik uchun delay
                await asyncio.sleep(random.uniform(2, 4))
                
            except errors.FloodWaitError as fe:
                print(f"⏳ FloodWait: {fe.seconds} soniya...")
                await asyncio.sleep(fe.seconds)
            except Exception as e:
                error_count += 1
                print(f"❌ {first_name} (@{username}) - xato: {e}")
                await asyncio.sleep(1)
        
        # Natija
        print()
        print("=" * 70)
        print("✅ TUGADI!")
        print("=" * 70)
        print(f"📇 Saqlangan: {saved_count} ta")
        print(f"⏭️ O'tkazildi: {skipped_count} ta (username yo'q)")
        print(f"❌ Xatolar: {error_count} ta")
        print("=" * 70)
        print()
        print("📱 Telegram Contacts ilovasini tekshiring!")
        print("   https://web.telegram.org/a/ → Contacts")
        
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print("👸 OISHA: Username bilan Telegram Contacts-ga Saqlash")
    print("=" * 70)
    print()
    print("📝 TELEFON YO'Q foydalanuvchilarni username orqali saqlaydi")
    print()
    
    asyncio.run(save_contacts_by_username())
