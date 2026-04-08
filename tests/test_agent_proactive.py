
import asyncio
import logging
import os
import sys
from typing import Dict
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from database import Database
from controllers.message_controller import MessageController

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_proactive_behavior():
    print("PROACTIVE AGENT TESTINI BOSHLAYAPMIZ...")
    
    api_keys = {
        "gemini": os.getenv("GEMINI_API_KEY")
    }
    
    if not api_keys["gemini"]:
        print("[ERROR] GEMINI_API_KEY topilmadi!")
        return

    # 1. Controller va Database
    db = Database()
    controller = MessageController(api_keys, db=db)
    
    # Fake bot_app (notificator uchun, shunchaki print qiladigan mock)
    class MockBotApp:
        class MockBot:
            async def send_message(self, chat_id, text, **kwargs):
                print(f"\n[MOCK BOT NOTIFICATION] To: {chat_id}\nMessage: {text}\n")
        bot = MockBot()
    
    controller.set_bot_app(MockBotApp())

    # 2. Test Message (Lead + Task Trigger)
    user_id = 999999 # Fake client ID
    user_name = "Test Client"
    message = "Salom! Menga yangi fast-food brendi uchun logotip va nom kerak. Baxtiyor aka bilan gaplashmoqchi edim. Telefonim: +998901234567"
    
    print(f"\n[USER]: {message}")
    print("[AI] AI o'ylamoqda va harakat qilmoqda...")
    
    response = await controller.get_response(user_id, user_name, message)
    
    print(f"\nAI JAVOBI: {response}")
    
    # 3. Bazani tekshirish (Vazifa ochildimi?)
    print("\n[DEBUG] Bazani tekshirish...")
    all_tasks = db.get_all_tasks(limit=5)
    print(f"Jami vazifalar (oxirgi 5 ta): {all_tasks}")
    
    agent_actions = db.get_recent_agent_actions(limit=5)
    print(f"Agent amallari (oxirgi 5 ta): {agent_actions}")
    
    if all_tasks:
        last_task = all_tasks[0]
        print(f"\nOK: VAZIFA BAZADA TOPILDI!")
        print(f"ID: {last_task['id']}")
        print(f"Title/Desc: {last_task['description']}")
        print(f"Assigned To: {last_task['assigned_to']}")
    else:
        print("\n[ERROR] Vazifa bazada yaratilmadi.")

if __name__ == "__main__":
    asyncio.run(test_proactive_behavior())
