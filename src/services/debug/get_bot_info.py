
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

async def get_info():
    token = os.getenv("BOT_TOKEN")
    bot = Bot(token=token)
    me = await bot.get_me()
    print(f"BOT_USERNAME: @{me.username}")
    print(f"BOT_NAME: {me.first_name}")

if __name__ == "__main__":
    asyncio.run(get_info())
