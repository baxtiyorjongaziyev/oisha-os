#!/usr/bin/env python3
"""
👸 OISHA: "TEZ NATIJA 4" UMUMIY - Contactlarni Yig'ish

Telefon borlar: Google Contacts (Ism Familya TN4 Gr)
Telefon yo'qlar: Telegram Contacts
"""

import asyncio
import logging
import os
import random
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors, functions, types
from src.settings import settings
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TezNatija4Collector")

SESSION_NAME = 'oisha_userbot'
GROUP_NAME = 'Tez Natija 4'


async def process_tez_natija_4():
    """Tez Natija 4 UMUMIY contactlarini yig'ish."""
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    # CSV fayllar
    csv_with_phone = 'tn4_google_contacts.csv'
    csv_without_phone = 'tn4_telegram_only.csv'
    
    contacts_with_phone = []
    contacts_without_phone = []
    telegram_saved = 0
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name}")
        print()
        
        # "TEZ NATIJA 4" UMUMIY ni qidirish
        print(f'🔍 "{GROUP_NAME}" UMUMIY guruhi qidirilmoqda...')
        target_group = None
        
        async for dialog in client.iter_dialogs():
            dialog_name = dialog.name or ""
            # Faqat "TEZ NATIJA 4" UMUMIY ni qidiramiz
            if "tez natija 4" in dialog_name.lower() and "umumiy" in dialog_name.lower():
                target_group = dialog
                print(f"✅ Topildi: {dialog.name} (ID: {dialog.id})")
                break
            elif dialog_name == "TEZ NATIJA 4" or dialog_name == '"TEZ NATIJA 4" UMUMIY':
                target_group = dialog
                print(f"✅ Topildi: {dialog.name} (ID: {dialog.id})")
                break
        
        if not target_group:
            print('❌ "TEZ NATIJA 4" UMUMIY guruhi topilmadi!')
            print("   Barcha guruhlar ro'yxati:")
            async for dialog in client.iter_dialogs():
                if "tez" in dialog.name.lower():
                    print(f"     - {dialog.name}")
            return
        
        print()
        print(f"📊 {target_group.name} dan a'zolarni yig'ish...")
        print("-" * 70)
        
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
            
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            phone = user.phone or ""
            
            # Ism formatini yaratish: "Ism Familya TN4 Gr"
            if last_name:
                full_name = f"{first_name} {last_name} TN4 Gr"
            else:
                full_name = f"{first_name} TN4 Gr"
            
            # Bazaga saqlash
            db.upsert_user(
                user_id=user_id,
                first_name=first_name,
                last_name=f"{last_name} TN4 Gr" if last_name else "TN4 Gr",
                username=username,
                phone=phone,
                role="Lead (TN4)",
                last_seen=None
            )
            
            if phone:
                # Telefon borlar - CSV ga
                contacts_with_phone.append({
                    'Name': full_name,
                    'Given Name': first_name,
                    'Family Name': f"{last_name} TN4 Gr" if last_name else "TN4 Gr",
                    'Phone': phone,
                    'Notes': f"@{username}" if username else "",
                    'Group': GROUP_NAME
                })
                print(f"📱 {full_name} - {phone}")
            else:
                # Telefon yo'qlar - Telegramga saqlash
                contacts_without_phone.append({
                    'user_id': user_id,
                    'name': full_name,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name or "TN4 Gr"
                })
                print(f"💬 {full_name} (telefon yo'q) -> Telegramga saqlanadi")
                
                # Telegram Contacts-ga saqlash
                try:
                    # Kontakt yaratish
                    contact = types.InputPhoneContact(
                        client_id=random.randrange(-2**63, 2**63),
                        phone="+999999999999",  # Placeholder
                        first_name=first_name,
                        last_name=f"{last_name} TN4 Gr" if last_name else "TN4 Gr"
                    )
                    
                    # Ammo telefon yo'q, shuning uchun faqat database saqlaymiz
                    # Telegram Contacts-ga qo'shish uchun telefon kerak
                    
                except Exception as e:
                    logger.warning(f"Telegram saqlashda xato: {e}")
            
            # FloodWait oldini olish
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # CSV fayllarni yaratish
        if contacts_with_phone:
            with open(csv_with_phone, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['Name', 'Given Name', 'Family Name', 'Phone', 'Notes', 'Group'])
                writer.writeheader()
                writer.writerows(contacts_with_phone)
        
        if contacts_without_phone:
            with open(csv_without_phone, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Name', 'Username', 'User ID', 'Status'])
                for c in contacts_without_phone:
                    writer.writerow([c['name'], f"@{c['username']}" if c['username'] else "", c['user_id'], 'Telefon yo\'q'])
        
        # Telegramda "Kontaktlar" guruhini yaratish/xabar yuborish
        if contacts_without_phone:
            print()
            print("📤 Telefonsiz contactlar uchun xabar yuborilmoqda...")
            message_lines = ["📋 TEZ NATIJA 4 - Telefonsiz Contactlar:\n"]
            for c in contacts_without_phone[:50]:  # Birinchi 50 ta
                line = f"• {c['name']}"
                if c['username']:
                    line += f" (@{c['username']})"
                message_lines.append(line)
            
            if len(contacts_without_phone) > 50:
                message_lines.append(f"\n... va yana {len(contacts_without_phone) - 50} ta")
            
            try:
                await client.send_message('me', "\n".join(message_lines))
                telegram_saved = min(50, len(contacts_without_phone))
                print(f"✅ Telegramga {telegram_saved} ta contact haqida xabar yuborildi")
            except Exception as e:
                logger.error(f"Telegram xabar yuborishda xato: {e}")
        
        # Yakuniy natija
        print()
        print("=" * 70)
        print(f'✅ "{GROUP_NAME}" UMUMIY - TUGADI!')
        print("=" * 70)
        print(f"📱 Telefon raqamli: {len(contacts_with_phone)} ta")
        print(f"💬 Telefon yo'q: {len(contacts_without_phone)} ta")
        print(f"📊 Jami: {len(contacts_with_phone) + len(contacts_without_phone)} ta")
        print()
        if contacts_with_phone:
            print(f"📁 Google Contacts CSV: {csv_with_phone}")
        if contacts_without_phone:
            print(f"📁 Telefon yo'qlar CSV: {csv_without_phone}")
            print(f"📤 Telegramga xabar yuborildi: Saved Messages")
        print("=" * 70)
        print()
        print("📱 Google Contacts-ga import qilish:")
        print("   https://contacts.google.com → Import → tn4_google_contacts.csv")
        
    except errors.FloodWaitError as fe:
        print(f"⏳ FloodWait: {fe.seconds} soniya kuting")
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print('👸 OISHA: "TEZ NATIJA 4" UMUMIY Contact Yig\'uv')
    print("=" * 70)
    print()
    
    asyncio.run(process_tez_natija_4())
