import asyncio
import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.settings import settings
from src.schedulers.cloud_brain_synthesizer import run_brain_synthesizer_cycle
from telethon import TelegramClient
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)

async def main():
    bot_token = settings.BOT_TOKEN.get_secret_value()
    bot_client = TelegramClient(StringSession(), settings.API_ID, settings.API_HASH)
    await bot_client.start(bot_token=bot_token)
    
    await run_brain_synthesizer_cycle(bot_client, settings.TEAM_GROUP_ID)
    
    await bot_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
