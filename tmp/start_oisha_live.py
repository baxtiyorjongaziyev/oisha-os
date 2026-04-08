
import asyncio
import os
import sys
import logging
from telethon import TelegramClient

# App root-ga o'tish
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.settings import settings

# Logger sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Oisha_Live")

async def send_team_greet():
    """Jamoa guruhiga salom xabarini yuborish."""
    if not settings.TEAM_GROUP_ID:
        logger.error("❌ TEAM_GROUP_ID topilmadi! .env ni tekshiring.")
        return

    # Userbot (shaxsiy akkaunt) orqali yuboramiz (chunki u guruhda bor)
    client = TelegramClient(
        os.path.join("data", "oisha_session"), 
        settings.API_ID, 
        settings.API_HASH
    )
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Session autorizatsiyadan o'tmagan! main.py ni birinchi marta qo'lda ishga tushiring.")
            return

        logger.info(f"👸 Oisha 'Jon Branding Team' ({settings.TEAM_GROUP_ID}) guruhiga ulanmoqda...")
        
        # Chiroyli salom xabari (AI-ga o'xshash, lekin biz hozir qo'lda yozamiz)
        greet_msg = (
            "👸 **Oisha Enterprise OS: Tizim Faol!** 🛡️\n\n"
            "Assalomu alaykum, Jon Branding jamoasi! 👰👑\n"
            "Men @baxtiyor_uz tomonidan barcha loyihalarni 24/7 nazorat qilish, "
            "sizlarni g'alabalar bilan tabriklash va ish jarayonini osonlashtirish uchun ruxsat oldim.\n\n"
            "🚀 **Vazifalarim:**\n"
            "1. 📈 Yangi lidlar haqida guruhga xabar berish.\n"
            "2. 🏆 Yopilgan bitimlar uchun menejerlarni tabriklash.\n"
            "3. ⏳ Muddati tugayotgan loyihalarni eslatish.\n"
            "4. 🧠 Savollaringizga AI yordamida javob berish (@oisha_bot ni mention qiling).\n\n"
            "Ishga tayyorman! Olg'a! 👸🛡️🕵️‍♀️"
        )
        
        await client.send_message(settings.TEAM_GROUP_ID, greet_msg)
        logger.info("✅ Salom xabari guruhga yuborildi!")
        
    except Exception as e:
        logger.error(f"❌ Salom xabarida xato: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Avval salom yuboramiz, keyin botni ishga tushirish uchun yo'riqnoma beramiz
    asyncio.run(send_team_greet())
