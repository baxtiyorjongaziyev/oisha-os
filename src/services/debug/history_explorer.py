
import os
import asyncio
import logging
import datetime
from telethon import TelegramClient, types
from dotenv import load_dotenv
from database import Database
from learning_engine import LearningEngine

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "history_analyzer_session"

class HistoryExplorer:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
        self.db = Database()
        self.api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY")
        }
        self.learner = LearningEngine(self.api_keys, self.db)

    async def analyze_history(self, start_date: datetime.datetime):
        """2025-yildan boshlab barcha xususiy suhbatlarni tahlil qilish."""
        await self.client.connect()
        if not await self.client.is_user_authorized():
            logger.error("Session not authorized!")
            return

        logger.info(f"Skanerlash boshlandi: {start_date.year}-yildan hozirgacha...")
        
        # 1. Barcha dialoglarni olish
        async for dialog in self.client.iter_dialogs():
            if not dialog.is_user: continue # Faqat shaxsiy chatlar
            
            user_entity = dialog.entity
            user_name = (user_entity.first_name or "") + " " + (user_entity.last_name or "")
            logger.info(f"Tahlil qilinmoqda: {user_name} (ID: {user_entity.id})")
            
            chat_context = []
            async for msg in self.client.iter_messages(user_entity, limit=50, offset_date=None):
                if msg.date.replace(tzinfo=None) < start_date:
                    break
                
                role = "user" if msg.out else "client"
                chat_context.append(f"{role}: {msg.text}")
            
            if chat_context:
                # Teskari tartibda (eskidan yangiga)
                chat_context.reverse()
                context_str = "\n".join(chat_context)
                
                # AI orqali uslub va bilimlarni o'rganish
                logger.info(f"AI tahlili: {user_name}...")
                await self.learner.analyze_and_learn(user_entity.id, context_str)
                
        logger.info("Tarixiy tahlil yakunlandi! Bot endi yanada aqlli.")

if __name__ == "__main__":
    explorer = HistoryExplorer()
    # 2025-yil 1-yanvardan boshlab
    start_point = datetime.datetime(2025, 1, 1)
    asyncio.run(explorer.analyze_history(start_point))
