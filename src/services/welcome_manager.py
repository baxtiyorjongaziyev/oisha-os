import logging
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class WelcomeManager:
    """
    Yangi lidlar uchun birinchi 'WOW' xabarini yuborish servisi.
    """
    def __init__(self, client: TelegramClient):
        self.client = client
        self.PORTFOLIO_LINK = "https://jonbranding.uz/uz/portfolio" 
        self.WELCOME_TEMPLATE = (
            "Assalomu alaykum! 👸🛡️\n\n"
            "Jon Branding agentligiga murojaat qilganingiz uchun rahmat. "
            "Biz sizning so'rovingizni qabul qildik va hozirda tahlil qilmoqdamiz.\n\n"
            "Tez orada strategik menejerimiz siz bilan bog'lanadi. "
            "Ungacha bizning eng sara ishlarimiz bilan tanishib chiqishingiz mumkin:\n"
            f"🔗 {self.PORTFOLIO_LINK}\n\n"
            "Sifat va natija — bizning ustuvor vazifamiz! 👸📈"
        )

    async def send_welcome(self, user_id: int):
        """Yangi mijozga xush kelibsiz xabari yuborish."""
        try:
            # Xavfsizlik uchun faqat biz javob bergan (out=True) bo'lsak yoki lid deb topilsa yuboramiz
            await self.client.send_message(user_id, self.WELCOME_TEMPLATE)
            logger.info(f"[WELCOME] Elite greeting sent to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"[WELCOME ERROR] {e}")
            return False
