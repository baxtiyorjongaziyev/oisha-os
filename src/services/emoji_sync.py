import asyncio
import logging
from telegram import Bot
from config import OWNER_ID, EMOJI_STATUS_MAPPING
from gcalendar import GoogleCalendarSync
import os
from dotenv import load_dotenv

load_dotenv()

# Logger sozlash
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def sync_emoji_status():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("[EMOJI SYNC] BOT_TOKEN topilmadi.")
        return

    bot = Bot(token=bot_token)
    calendar = GoogleCalendarSync()
    
    logger.info("[EMOJI SYNC] Xizmat ishga tushdi...")

    while True:
        try:
            # 1. Kalendardan hozirgi tadbirni olish
            event = calendar.get_current_event()
            
            emoji_id = EMOJI_STATUS_MAPPING["available"]
            
            if event:
                summary = event.get("summary", "").lower()
                logger.info(f"[EMOJI SYNC] Tadbir topildi: {summary}")
                
                # Oddiy keyword matching
                if "meeting" in summary or "uchrashuv" in summary:
                    emoji_id = EMOJI_STATUS_MAPPING["meeting"]
                elif "work" in summary or "ish" in summary:
                    emoji_id = EMOJI_STATUS_MAPPING["work"]
                else:
                    emoji_id = EMOJI_STATUS_MAPPING["busy"]
            
            # 2. Telegram statusni yangilash
            # DIQQAT: bot.set_user_emoji_status() permission talab qiladi
            try:
                # Agar emoji_id None bo'lsa, status o'chiriladi
                await bot.set_user_emoji_status(
                    user_id=OWNER_ID,
                    custom_emoji_id=emoji_id
                )
                logger.info(f"[EMOJI SYNC] Status yangilandi: {emoji_id}")
            except Exception as te:
                logger.warning(f"[EMOJI SYNC] Statusni o'zgartirib bo'lmadi (Permission?): {te}")
                
        except Exception as e:
            logger.error(f"[EMOJI SYNC ERROR] {e}")

        # Har 5 daqiqada tekshirish
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(sync_emoji_status())
