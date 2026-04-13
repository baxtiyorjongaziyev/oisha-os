import asyncio
import logging
import os
import sys
from database import Database
from learning_engine import LearningEngine
import config

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_bulk_learning():
    db = Database()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.error("GEMINI_API_KEY topilmadi!")
        return

    learner = LearningEngine(gemini_key, db)
    
    # Barcha foydalanuvchilarni olish
    users = db.get_all_users()
    logger.info(f"Jami {len(users)} ta foydalanuvchi topildi. O'rganishni boshlaymiz...")

    total_learned = 0
    for user_id in users:
        # Foydalanuvchi ma'lumotlarini olish
        user_info = db.get_user_info(user_id)
        name = user_info.get("first_name", f"User {user_id}") if user_info else f"User {user_id}"
        
        logger.info(f"Foydalanuvchi tahlil qilinmoqda: {name} ({user_id})")
        
        # Xabarlar tarixini olish
        history = db.get_recent_messages(user_id, limit=2000) # Iloji boricha ko'proq xabar
        
        if not history:
            logger.info(f"Foydalanuvchi ({user_id}) uchun xabarlar topilmadi.")
            continue
            
        logger.info(f"Foydalanuvchi ({user_id}) uchun {len(history)} ta xabar topildi.")
        
        # AI orqali tahlil qilish (chunks - qismlarga bo'lib, AI context limitdan oshib ketmasligi uchun)
        # 10 ta xabardan qilib tahlil qilamiz
        chunk_size = 10
        for i in range(0, len(history), chunk_size):
            chunk = history[i:i + chunk_size]
            added = await learner.analyze_and_learn(user_id, chunk)
            total_learned += added
            if added > 0:
                logger.info(f"Foydalanuvchi ({user_id}) dan {added} ta yangi fakt o'rganildi.")
            
            # AI API limitlari uchun biroz kutish
            await asyncio.sleep(1)

    logger.info(f"Ommaviy o'rganish yakunlandi! Jami {total_learned} ta yangi fakt bazaga qo'shildi.")

if __name__ == "__main__":
    asyncio.run(run_bulk_learning())
