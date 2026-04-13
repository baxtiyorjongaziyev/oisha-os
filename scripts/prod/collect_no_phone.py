#!/usr/bin/env python3
"""
👸 OISHA: Telefon Yo'q Contactlarni Yig'ish

Telefon raqami yo'q foydalanuvchilarni ro'yxatga oladi va 
"Saved Messages" ga yuboradi (qo'lda qo'shish uchun).
"""

import asyncio
import logging
import os
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors
from src.settings import settings
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NoPhoneContacts")

SESSION_NAME = 'oisha_userbot'
GROUP_NAME = 'Tez Natija 4'


async def collect_no_phone_users():
    """Telefon raqami yo'q foydalanuvchilarni yig'ish."""
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    no_phone_users = []
    
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
        print(f"📊 Telefon yo'q foydalanuvchilarni yig'ish...")
        print("-" * 70)
        
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
            
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            username = user.username or ""
            phone = user.phone
            user_id = user.id
            
            # Bazaga saqlash
            db.upsert_user(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                phone="",
                role="Lead (No Phone)",
                last_seen=None
            )
            
            if not phone:
                # Telefon yo'q - ro'yxatga olish
                user_info = {
                    'user_id': user_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'username': username,
                    'display_name': f"{first_name} {last_name}".strip() or "NoName"
                }
                no_phone_users.append(user_info)
                print(f"💬 {user_info['display_name']} (@{username}) - telefon yo'q")
        
        # CSV fayl yaratish
        if no_phone_users:
            csv_file = 'tn4_no_phone_users.csv'
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['display_name', 'username', 'user_id', 'first_name', 'last_name'])
                writer.writeheader()
                writer.writerows(no_phone_users)
            print(f"\n📁 CSV fayl: {csv_file}")
        
        # Telegram Saved Messages ga yuborish
        if no_phone_users:
            print(f"\n📤 Saved Messages ga yuborilmoqda...")
            
            # Xabarni bo'lib yuborish (Telegram limit: 4096 belgi)
            header = f"📋 <b>TEZ NATIJA 4 - Telefon Yo'q Contactlar</b>\n"
            header += f"Jami: {len(no_phone_users)} ta\n"
            header += "-" * 50 + "\n\n"
            
            messages = [header]
            current_msg = header
            
            for i, user in enumerate(no_phone_users, 1):
                line = f"{i}. <b>{user['display_name']}</b>"
                if user['username']:
                    line += f" - @{user['username']}"
                line += f" (ID: {user['user_id']})\n"
                
                # Agar xabar uzun bo'lsa, yangi xabar boshlaymiz
                if len(current_msg + line) > 4000:
                    messages.append(current_msg)
                    current_msg = line
                else:
                    current_msg += line
            
            messages.append(current_msg)
            
            # Xabarlarni yuborish
            for msg in messages:
                try:
                    await client.send_message('me', msg, parse_mode='html')
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Xabar yuborishda xato: {e}")
            
            print(f"✅ Saved Messages ga {len(messages)} ta xabar yuborildi")
            print(f"   Telefon raqamini olish uchun shaxsan yozing!")
        
        # Natija
        print()
        print("=" * 70)
        print("✅ TUGADI!")
        print("=" * 70)
        print(f"💬 Telefon yo'q: {len(no_phone_users)} ta")
        print()
        print("📱 Qo'lda kontakt qo'shish uchun:")
        print("   1. Saved Messages (Saqlangan xabarlar) ni oching")
        print("   2. Har bir foydalanuvchi uchun:")
        print("      - Profilga kiring (@username)")
        print("      - Telefon raqamini so'rang")
        print("      - 'Add Contact' tugmasini bosing")
        print("=" * 70)
        
    except errors.FloodWaitError as fe:
        print(f"⏳ FloodWait: {fe.seconds} soniya kuting")
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print("👸 OISHA: Telefon Yo'q Contactlarni Yig'ish")
    print("=" * 70)
    print()
    
    asyncio.run(collect_no_phone_users())
