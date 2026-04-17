
import asyncio
import logging
import datetime
from src.database import Database
from src.services.core.action_parser import ActionParser
from src.services.core.singularity_core import ProactiveWorker
from src import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_task_extraction():
    db = Database()
    await db.init_instance()
    
    # 1. Simulate a conversation
    chat_id = 12345
    messages = [
        (chat_id, "Inomjon, ertaga soat 10:00 gacha Dilorom opaning logotipini tayyorlab qo'yishing kerak.", False),
        (chat_id, "Xo'p bo'ladi, Muhammadjon aka.", False)
    ]
    
    for uid, text, is_ai in messages:
        await db.log_message(uid, text, is_ai)
    
    logger.info("✅ Conversation logged.")

    # 2. Test ActionParser with [TASK] tag simulation
    parser = ActionParser(db=db)
    sample_reply = "Xo'p bo'ladi. [TASK: title=Dilorom opa logotipini tayyorlash|assigned_to=Inomjon|deadline=2026-04-17]"
    
    logger.info("Testing ActionParser [TASK] tag...")
    # Mocking sender_id as Muhammadjon (Admin/Owner)
    clean_text = await parser.parse_and_execute(sample_reply, sender_id=int(config.OWNER_ID or 0))
    
    logger.info(f"Clean text: {clean_text}")
    
    # Check DB
    async with (await db.get_connection()).execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 1") as cursor:
        task = await cursor.fetchone()
        if task:
            logger.info(f"✅ Task successfully created in DB: {task}")
        else:
            logger.error("❌ Task NOT found in DB!")

    # 3. Test ProactiveWorker Task Extraction logic
    # Note: This requires a real Gemini API Key to work fully
    worker = ProactiveWorker(db_instance=db)
    # We won't run analyze_and_extract_tasks here to avoid API dependency in test
    # but we verified the DB and Parser logic.

if __name__ == "__main__":
    asyncio.run(test_task_extraction())
