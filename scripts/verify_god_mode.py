import asyncio
import os
import sys
import logging

# [CRITICAL] Ensure local modules are discoverable
sys.path.append(os.getcwd())

from src.controllers.message_controller import MessageController
from src.services.gemini_advisor import AdvisorAgent
from src.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_god_mode():
    db = Database()
    advisor = AdvisorAgent()
    controller = MessageController(db=db, advisor_agent=advisor)
    
    # 1. Test "Isituvchi" prompt
    test_msg = "Menga jonbranding xizmatlari kerak, hamkor bo'lishimiz mumkinmi?"
    
    logger.info(f"👸 [TEST] Analyzing message: '{test_msg}'")
    intent = await controller.process_update(type('Event', (object,), {'text': test_msg, 'chat_id': 123456}))
    
    logger.info(f"👸 [RESULT] AI Classified Intent: {intent}")
    
    if intent in ["VIP_CLIENT", "PARTNER", "HOT_LEAD"]:
        logger.info("✅ SUCCESS: Oisha-OS God Mode correctly identified a high-value lead!")
    else:
        logger.warning(f"⚠️ Result '{intent}' is not what we expected. Check AI prompt.")

if __name__ == "__main__":
    asyncio.run(test_god_mode())
