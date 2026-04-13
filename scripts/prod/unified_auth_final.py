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
    if len(sys.argv) < 3:
        print("ERROR: Code and/or Hash not provided.")
        return
    
    code = sys.argv[1].strip()
    phone_code_hash = sys.argv[2].strip()
    
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Finalizing unified sign-in for {PHONE}...")
        try:
            await client.sign_in(PHONE, code, password=PASSWORD, phone_code_hash=phone_code_hash)
            print("AUTH_SUCCESS_UNIFIED")
        except Exception as e:
            print(f"ERROR: {str(e)}")
    else:
        print("ALREADY_AUTHORIZED")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
