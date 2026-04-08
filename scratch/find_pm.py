
import asyncio
import os
import logging
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

async def main():
    client = TelegramClient("oisha_userbot", API_ID, API_HASH)
    await client.connect()
    
    try:
        # Try to resolve @jonbranding_pm
        target = await client.get_entity("@jonbranding_pm")
        print(f"FOUND: {target.id} | {target.first_name} | {target.username}")
    except Exception as e:
        print(f"NOT FOUND: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
