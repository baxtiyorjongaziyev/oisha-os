import os
from telethon import TelegramClient
import sys

# Load credentials from .env context
API_ID = 30643078
API_HASH = 'e5850001c1d86ac0fb439fbd8319cb7f'
PHONE = '+998336450097'

async def main():
    if len(sys.argv) < 2:
        print("ERROR: No code provided.")
        return
    
    code = sys.argv[1].strip()
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Finalizing sign-in for {PHONE} with code {code}...")
        try:
            await client.sign_in(PHONE, code)
            print("AUTH_SUCCESS")
        except Exception as e:
            print(f"ERROR: {str(e)}")
    else:
        print("ALREADY_AUTHORIZED")
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
