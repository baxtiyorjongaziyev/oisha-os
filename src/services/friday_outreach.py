import asyncio
import random
import logging
from telethon import TelegramClient, events
from settings import settings

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Telegram Client Initialization
    client = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH)
    await client.start()
    
    # Progress tracking
    sent_file = "outreach_progress.json"
    sent_users = set()
    if os.path.exists(sent_file):
        with open(sent_file, "r") as f:
            sent_users = set(json.load(f))

    group_identifier = "Tez Natija 5" 
    friday_message = (
        "Assalomu alaykum! Juma ayyomingiz muborak bo'lsin. ✨\n\n"
        "Men Baxtiyorning (Jon Branding agentligi asoschisi) raqamli yordamchisi Oishaman. 🤖\n\n"
        "Biz 'Tez Natija 5' guruhida birgamiz. Sizning biznesingiz uchun professional brending, "
        "logo yoki strategiya kerak bo'lsa, men har doim yordamga tayyorman. \n\n"
        "Hozirda biz bir nechta tadbirkorlar uchun **bepul strategik sessiya** o'tkazyapmiz. "
        "Agar qiziqsangiz, shunchaki 'Ha' deb javob bering, batafsil ma'lumot yuboraman! 😊"
    )

    try:
        group = None
        async for dialog in client.iter_dialogs():
            if group_identifier in dialog.name:
                group = dialog
                break
        
        if not group:
            logger.error(f"❌ '{group_identifier}' guruhi topilmadi.")
            return

        logger.info(f"✅ Guruh: {group.name}. A'zolar ro'yxati yuklanmoqda...")
        participants = await client.get_participants(group)
        
        count = 0
        for user in participants:
            if user.bot or user.is_self or user.id in sent_users:
                continue
            
            try:
                # Random delay: 60-120 seconds to be safe
                delay = random.randint(60, 120)
                logger.info(f"⏳ {user.first_name} (@{user.username or 'no_user'}) ga yuborishdan oldin {delay}s kutilmoqda...")
                await asyncio.sleep(delay)
                
                await client.send_message(user.id, friday_message)
                count += 1
                sent_users.add(user.id)
                
                # Save progress
                with open(sent_file, "w") as f:
                    json.dump(list(sent_users), f)
                
                logger.info(f"✅ [{count}] Yuborildi: {user.first_name}")
                
                if count >= 400:
                    break
                    
            except Exception as e:
                logger.error(f"⚠️ {user.first_name} ga yuborishda xato: {e}")
                if "FloodWaitError" in str(e):
                    wait_time = int(re.search(r'wait (\d+)', str(e)).group(1)) + 60
                    logger.warning(f"❌ Flood detected! Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    await asyncio.sleep(180) 

        logger.info(f"🏁 Yakunlandi! Jami {count} yangi xabar yuborildi.")

    except Exception as e:
        logger.error(f"❌ Xatolik: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
