import os
from telethon import TelegramClient
import sys

# Load credentials from .env context
API_ID = 30643078
API_HASH = '***REDACTED***'
PHONE = '+998336450097'

async def main():
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Sending code to {PHONE}...")
        try:
            await client.send_code_request(PHONE)
            print("CODE_SENT_SUCCESSFULLY")
        except Exception as e:
            print(f"ERROR: {str(e)}")
    else:
        print("ALREADY_AUTHORIZED")
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
