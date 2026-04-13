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
logger = logging.getLogger("GroupContactsSaver")

async def save_group_members_to_google_contacts(target_group_name: str):
    """Guruh a'zolarini skanerlash va Google Contacts-ga saqlash."""
    db = Database()
    gcontacts = GoogleContactsSync()
    session_path = 'userbot_session'
    
    client = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH)
    
    saved_count = 0
    skipped_count = 0
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Userbot authorized emas! Session faylini tekshiring.")
            return

        logger.info(f"🔍 '{target_group_name}' guruhi qidirilmoqda...")
        target_group = None
        
        async for dialog in client.iter_dialogs():
            if target_group_name.upper() in dialog.name.upper():
                target_group = dialog
                logger.info(f"✅ Guruh topildi: {dialog.name} (ID: {dialog.id})")
                break
        
        if not target_group:
            logger.error(f"❌ '{target_group_name}' guruhi topilmadi.")
            return

        logger.info(f"🚀 Guruh a'zolari skanerlanmoqda: {target_group.name}")
        
        async for user in client.iter_participants(target_group.id):
            if user.bot:
                continue
                
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or "Unknown"
            last_name = user.last_name or ""
            phone = user.phone
            
            # 1. Bazaga saqlash
            db.upsert_user(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                phone=phone,
                role="Lead (Scraped)",
                last_seen=None
            )
            
            # 2. Google Contacts-ga saqlash (faqat telefon bor bo'lsa)
            if phone:
                note = f"Guruh: {target_group.name}\nTelegram: @{username if username else 'N/A'}\nID: {user_id}"
                
                success = gcontacts.create_contact(
                    first_name=first_name,
                    last_name=last_name or f"{target_group.name}",
                    phones=[phone],
                    note=note,
                    group_name=target_group.name
                )
                
                if success:
                    saved_count += 1
                    logger.info(f"✅ Saqlandi: {first_name} ({phone})")
                else:
                    skipped_count += 1
                    logger.warning(f"⚠️ Saqlanmadi: {first_name}")
            else:
                skipped_count += 1
                logger.info(f"⏭️ Telefon yo'q: {first_name} {last_name} (@{username})")
            
            # Xavfsizlik uchun delay
            await asyncio.sleep(random.uniform(2, 4))
            
            if (saved_count + skipped_count) % 10 == 0:
                logger.info(f"📊 Jarayon: {saved_count} saqlandi, {skipped_count} o'tkazib yuborildi")
        
        logger.info(f"""
✨ TUGADI!
📊 Statistika:
   ✅ Google Contacts-ga saqlandi: {saved_count}
   ⏭️ O'tkazib yuborildi (telefon yo'q/yangi emas): {skipped_count}
   📁 Guruh: '{target_group_name}'
        """)
        
    except errors.FloodWaitError as fe:
        logger.warning(f"⏳ FloodWait: {fe.seconds} soniya kutish kerak...")
        await asyncio.sleep(fe.seconds)
    except Exception as e:
        logger.error(f"❌ Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()
        logger.info("🔌 Aloqa uzildi.")

if __name__ == "__main__":
    # Tez Natija 4 guruhi
    TARGET_GROUP = "Tez natija 4"
    
    print("=" * 60)
    print("👸 Oisha: Tez Natija 4 - Google Contacts Sync")
    print("=" * 60)
    print(f"🎯 Guruh: {TARGET_GROUP}")
    print("📇 Google Contacts-ga saqlash boshlanmoqda...")
    print("-" * 60)
    
    asyncio.run(save_group_members_to_google_contacts(TARGET_GROUP))
