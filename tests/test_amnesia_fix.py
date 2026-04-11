import asyncio
import os
import pytest
from dotenv import load_dotenv
from database import Database

# userbot.py endi src/main.py ga ko'chirilgan
pytest.importorskip("userbot", reason="userbot module moved to src/main.py")

load_dotenv()

async def test_memory():
    # Setup test DB user
    db = Database("bot_database.db")
    test_user_id = 999111222
    db.upsert_user(test_user_id, "Test User", phone="+998901234567", service_type="Logotip vizitka", deadline="1 hafta")
    
    # Send a message to get reply
    print("Testing get_reply() with DB injected context...")
    
    # Initialize ai client in userbot explicitly since we're calling it directly
    from google import genai
    userbot.ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    userbot.db = db # Use our connected DB
    
    response = await userbot.get_reply(test_user_id, "Test User", message_text="Meni ismim va raqamim nima edi?")
    print(f"AI Response: \n{response}")
    
if __name__ == "__main__":
    asyncio.run(test_memory())
