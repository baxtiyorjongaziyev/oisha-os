import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
PASSWORD = os.environ.get("TELEGRAM_PASSWORD", "")

async def main():
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Requesting NEW code for {PHONE}...")
        sent_code = await client.send_code_request(PHONE)
        phone_code_hash = sent_code.phone_code_hash
        print(f"HASH:{phone_code_hash}")
        print("WAITING_FOR_USER_NEW_CODE")
    else:
        print("ALREADY_AUTHORIZED")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
