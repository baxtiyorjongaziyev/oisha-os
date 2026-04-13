import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_id = os.getenv("TG_API_ID") 
    api_hash = os.getenv("TG_API_HASH")
    session = "oisha_userbot"

    client = TelegramClient(session, api_id, api_hash)
    await client.start()

    print("--- Searching for 'Jon Branding Team' ---")
    async for dialog in client.iter_dialogs():
        if dialog.is_group:
            print(f"Group: {dialog.name} | ID: {dialog.id}")
            if "Jon Branding Team" in dialog.name:
                print(f"MATCH FOUND! ID: {dialog.id}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
