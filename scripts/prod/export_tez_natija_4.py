"""
Oisha: Tez Natija 4 Guruh Contactlarini Google Contacts-ga Saqlash

AVVAL O'ZINGIZ AVTORIZATSIYA QILING:
  1. python authorize_userbot.py
  2. Telefon raqamingizni kiriting (masalan: +998901234567)
  3. Telegram dan kelgan kodni kiriting
  4. So'ngra contactlarni saqlash scriptini ishga tushiring
"""

import asyncio
import logging
import os
import random
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors
from src.database import Database
from src.settings import settings
from src.services.gcontacts import GoogleContactsSync

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TezNatija4Contacts")


async def save_tez_natija_4_contacts():
    """Tez Natija 4 guruhi a'zolarini Google Contacts-ga saqlash."""
    
    # Google Contacts ni sozlash
    gcontacts = GoogleContactsSync()
    if not gcontacts.service:
        logger.error("❌ Google Contacts ulanmadi. token.pickle yoki service_account.json tekshiring!")
        logger.info("   Yordam: https://developers.google.com/people/quickstart/python")
        return
    
    db = Database()
    client = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH)
    
    saved_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Userbot avtorizatsiya qilingan emas!")
            logger.info("   Avval authorize_userbot.py ni ishga tushiring!")
            return

        logger.info("🔍 'Tez Natija 4' guruhi qidirilmoqda...")
        target_group = None
        
        async for dialog in client.iter_dialogs():
            if "tez natija 4" in dialog.name.lower():
                target_group = dialog
                logger.info(f"✅ Guruh topildi: {dialog.name} (ID: {dialog.id})")
                break
        
        if not target_group:
            logger.error("❌ 'Tez Natija 4' guruhi topilmadi!")
            logger.info("   Guruhingiz nomini tekshiring (masalan: 'Tez natija 4', 'TEZ NATIJA 4')")
            return

        logger.info(f"🚀 {target_group.name} dan a'zolarni yig'ish...")
        logger.info("⏳ Bu jarayon bir necha daqiqa davom etishi mumkin...")
        
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
            
            # Google Contacts-ga saqlash (faqat telefon bor bo'lsa)
            if phone:
                note = f"📱 Telegram: @{username if username else 'yoq'}\n🆔 ID: {user_id}\n📂 Guruh: Tez Natija 4"
                
                try:
                    success = gcontacts.create_contact(
                        first_name=first_name,
                        last_name=last_name or "TN4",
                        phones=[phone],
                        note=note,
                        group_name="Tez Natija 4"
                    )
                    
                    if success:
                        saved_count += 1
                        logger.info(f"✅ Saqlandi: {first_name} {last_name} - {phone}")
                    else:
                        error_count += 1
                        logger.warning(f"⚠️ Xato: {first_name} - saqlanmadi")
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Google Contacts xato: {e}")
            else:
                skipped_count += 1
                logger.info(f"⏭️ O'tkazib yuborildi: {first_name} (telefon yo'q)")
            
            # Xavfsizlik uchun delay (FloodWait oldini olish)
            await asyncio.sleep(random.uniform(1.5, 3))
            
            if (saved_count + skipped_count + error_count) % 10 == 0:
                logger.info(f"📊 Jarayon: {saved_count} saqlandi | {skipped_count} o'tkazildi | {error_count} xato")
        
        # Yakuniy statistika
        logger.info("""
╔════════════════════════════════════════════════════════╗
║              ✅ TUGADI - TEZ NATIJA 4                   ║
╠════════════════════════════════════════════════════════╣
║  📇 Google Contacts-ga saqlandi:  {saved_count:>3} ta                  ║
║  ⏭️ Telefonsiz (o'tkazildi):    {skipped_count:>3} ta                  ║
║  ❌ Xatolar:                    {error_count:>3} ta                  ║
║  📊 Jami:                       {saved_count + skipped_count + error_count:>3} ta                  ║
╚════════════════════════════════════════════════════════╝
        """)
        
        logger.info("📱 Google Contacts ilovasini tekshiring!")
        
    except errors.FloodWaitError as fe:
        logger.warning(f"⏳ FloodWait: {fe.seconds} soniya kutish kerak...")
        logger.info("   Telegram limitga tushdingiz. Keyinroq qayta urining.")
    except Exception as e:
        logger.error(f"❌ Kutilmagan xato: {e}", exc_info=True)
    finally:
        await client.disconnect()
        logger.info("🔌 Aloqa uzildi.")


if __name__ == "__main__":
    print("=" * 70)
    print("👸 OISHA: Tez Natija 4 → Google Contacts Exporter")
    print("=" * 70)
    print()
    
    # Tekshirish
    if not os.path.exists('oisha_userbot.session'):
        print("❌ AVVAL AVTORIZATSIYA QILING!")
        print()
        print("Quyidagi buyruqni ishga tushiring:")
        print("   .venv_oi\\Scripts\\python -c \"import asyncio; from telethon import TelegramClient; from src.settings import settings; async def auth(): client = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH); await client.start(); print('OK'); await client.disconnect(); asyncio.run(auth())\"");
        print()
        print("So'ngra qayta urining.")
        sys.exit(1)
    
    # Google auth tekshirish
    if not os.path.exists('token.pickle') and not os.path.exists('service_account.json'):
        print("❌ Google Contacts avtorizatsiyasi topilmadi!")
        print()
        print("1. Google Cloud Console ga kiring:")
        print("   https://console.cloud.google.com/apis/credentials")
        print()
        print("2. 'Create Credentials' → 'OAuth client ID' → 'Desktop app'")
        print()
        print("3. client_secret_*.json faylini yuklab oling va 'service_account.json' deb nomlang")
        print()
        sys.exit(1)
    
    print("✅ Tekshiruvlar muvaffaqiyatli!")
    print("📇 Contactlarni saqlash boshlanmoqda...")
    print("-" * 70)
    
    asyncio.run(save_tez_natija_4_contacts())
