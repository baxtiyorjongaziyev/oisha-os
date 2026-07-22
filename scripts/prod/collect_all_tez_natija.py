#!/usr/bin/env python3
"""
👸 OISHA: TEZ NATIJA 2/3/4/5 - Barcha Contactlarni Yig'ish

Barcha guruhdagi contactlarni:
1. Telegram Contacts-ga saqlash (telefon bo'lmasa ham)
2. Alohida CSV fayllar (Google Contacts import uchun)
"""

import asyncio
import logging
import os
import random
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors, functions
from src.settings import settings
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TezNatijaAllGroups")

SESSION_NAME = 'oisha_userbot'

# Guruhlar ro'yxati
GROUPS = [
    ('"TEZ NATIJA 5" UMUMIY', 'TN5'),
    ('"TEZ NATIJA 4" UMUMIY', 'TN4'),
    ('"TEZ NATIJA 3" UMUMIY', 'TN3'),
    ('"TEZ NATIJA 2" UMUMIY', 'TN2'),
]


async def process_all_groups():
    """Barcha TEZ NATIJA guruhlarini qayta ishlash."""
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    all_results = {}
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name}")
        print()
        
        for group_full_name, group_label in GROUPS:
            print("=" * 70)
            print(f'👸 {group_full_name}')
            print("=" * 70)
            
            # Guruhni qidirish
            print(f'🔍 Guruh qidirilmoqda...')
            target_group = None
            
            async for dialog in client.iter_dialogs():
                dialog_name = dialog.name or ""
                # "TEZ NATIJA X" ni qidirish
                if f"tez natija {group_label[-1]}" in dialog_name.lower():
                    target_group = dialog
                    print(f"✅ Topildi: {dialog.name}")
                    break
            
            if not target_group:
                print(f'❌ {group_full_name} topilmadi!')
                all_results[group_label] = {'error': 'Guruh topilmadi'}
                continue
            
            # Guruh uchun ro'yxatlar
            phone_contacts = []
            telegram_saved = 0
            username_saved = 0
            no_username = 0
            
            print(f"📊 A'zolarni yig'ish...")
            print("-" * 70)
            
            async for user in client.iter_participants(target_group.id):
                if user.bot:
                    continue
                
                first_name = user.first_name or "NoName"
                last_name = user.last_name or ""
                username = user.username
                phone = user.phone
                user_id = user.id
                
                # Ism formati: "Ism Familya TN2 Gr"
                if last_name:
                    full_name = f"{first_name} {last_name} {group_label} Gr"
                    csv_last_name = f"{last_name} {group_label} Gr"
                else:
                    full_name = f"{first_name} {group_label} Gr"
                    csv_last_name = f"{group_label} Gr"
                
                # Bazaga saqlash
                db.upsert_user(
                    user_id=user_id,
                    first_name=first_name,
                    last_name=csv_last_name,
                    username=username or "",
                    phone=phone or "",
                    role=f"Lead ({group_label})",
                    last_seen=None
                )
                
                # Telefon borlar - CSV ro'yxatga
                if phone:
                    phone_contacts.append({
                        'Name': full_name,
                        'Given Name': first_name,
                        'Family Name': csv_last_name,
                        'Phone 1 - Value': phone,
                        'Phone 1 - Type': 'Mobile',
                        'Notes': f"@{username}" if username else f"{group_label} a'zosi",
                        'Labels': f'TEZ NATIJA {group_label[-1]}'
                    })
                
                # Telegram Contacts-ga saqlash (telefon bo'lmasa ham)
                try:
                    # 1. Avval telefon bilan urinish
                    if phone:
                        await client(functions.contacts.AddContactRequest(
                            id=user_id,
                            first_name=first_name,
                            last_name=csv_last_name,
                            phone=phone,
                            add_phone_privacy_exception=False
                        ))
                        telegram_saved += 1
                    # 2. Username bilan saqlash (agar telefon yo'q bo'lsa)
                    elif username:
                        user_entity = await client.get_entity(username)
                        await client(functions.contacts.AddContactRequest(
                            id=user_entity,
                            first_name=first_name,
                            last_name=csv_last_name,
                            phone="+",
                            add_phone_privacy_exception=False
                        ))
                        username_saved += 1
                    # 3. User ID bilan saqlash (agar username ham yo'q bo'lsa)
                    else:
                        await client(functions.contacts.AddContactRequest(
                            id=user_id,
                            first_name=first_name,
                            last_name=csv_last_name,
                            phone="+",
                            add_phone_privacy_exception=False
                        ))
                        no_username += 1
                    
                    status = "✅"
                except errors.FloodWaitError as fe:
                    print(f"⏳ FloodWait: {fe.seconds} soniya kutish...")
                    await asyncio.sleep(fe.seconds)
                    status = "⏳"
                except Exception as e:
                    status = "❌"
                    logger.warning(f"Saqlashda xato: {e}")
                
                if phone:
                    print(f"{status} {full_name} - {phone}")
                elif username:
                    print(f"{status} {full_name} (@{username}) - username bilan")
                else:
                    print(f"{status} {full_name} - ID bilan")
                
                # Delay
                await asyncio.sleep(random.uniform(1.5, 3))
            
            # CSV fayl yaratish
            if phone_contacts:
                csv_file = f'tn{group_label[-1]}_google_contacts.csv'
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['Name', 'Given Name', 'Family Name', 'Phone 1 - Value', 'Phone 1 - Type', 'Notes', 'Labels']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(phone_contacts)
                print(f"\n📁 CSV: {csv_file} ({len(phone_contacts)} ta)")
            
            # Natijani saqlash
            all_results[group_label] = {
                'phone_count': len(phone_contacts),
                'telegram_saved': telegram_saved,
                'username_saved': username_saved,
                'no_username': no_username,
                'csv_file': f'tn{group_label[-1]}_google_contacts.csv' if phone_contacts else None
            }
            
            print()
            print(f"📊 {group_label} NATIJA:")
            print(f"   📱 Telefon bilan: {len(phone_contacts)} ta")
            print(f"   💾 Telegramga: {telegram_saved + username_saved + no_username} ta")
            print()
            
            # Guruhlar o'rtasida tanaffus
            await asyncio.sleep(5)
        
        # Yakuniy xulosa
        print("=" * 70)
        print("✅ BARCHA GURUHLAR TUGADI!")
        print("=" * 70)
        print()
        
        for group_label, result in all_results.items():
            if 'error' in result:
                print(f"❌ {group_label}: {result['error']}")
            else:
                print(f"📊 {group_label}:")
                print(f"   📱 Telefon: {result['phone_count']} ta")
                print(f"   💾 Telegram: {result['telegram_saved'] + result['username_saved'] + result['no_username']} ta")
                if result['csv_file']:
                    print(f"   📁 CSV: {result['csv_file']}")
                print()
        
        print("=" * 70)
        print("📱 Google Contacts-ga import qilish:")
        print("   https://contacts.google.com → Import")
        print("   Har bir CSV faylni alohida import qiling")
        print("=" * 70)
        
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print("👸 OISHA: TEZ NATIJA 2/3/4/5 - Barcha Contactlar")
    print("=" * 70)
    print()
    print("📋 Barcha guruhdagi contactlarni:")
    print("   1. Telegram Contacts-ga saqlash")
    print("   2. Alohida CSV fayllar yaratish")
    print()
    
    asyncio.run(process_all_groups())
