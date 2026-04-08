
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

async def test_reach():
    token = os.getenv("BOT_TOKEN")
    owner_id = 5824905101
    group_id = -1002361131012
    
    bot = Bot(token=token)
    
    print(f"Testing bot: {token[:10]}...")
    
    # 1. Test Owner
    try:
        chat = await bot.get_chat(owner_id)
        print(f"Owner found: {chat.first_name}")
        await bot.send_message(chat_id=owner_id, text="TEST: Bot sizga bog'lana oladi!")
        print("Message sent to Owner.")
    except Exception as e:
        print(f"Owner Error: {e}")
        
    # 2. Test Group
    try:
        chat = await bot.get_chat(group_id)
        print(f"Group found: {chat.title}")
        await bot.send_message(chat_id=group_id, text="TEST: Bot guruhga bog'lana oladi!")
        print("Message sent to Group.")
    except Exception as e:
        print(f"Group Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_reach())
