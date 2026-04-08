import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import sys
import asyncio

# Load credentials from .env context
API_ID = 30643078
API_HASH = 'e5850001c1d86ac0fb439fbd8319cb7f'
PHONE = '+998336450097'
PASSWORD = 'Telegram0097'

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
