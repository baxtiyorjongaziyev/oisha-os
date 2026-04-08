import os
from telethon import TelegramClient
import asyncio
import sys

# Credentials
API_ID = 30643078
API_HASH = 'e5850001c1d86ac0fb439fbd8319cb7f'
PHONE = '+998336450097'

async def main():
    print(f"Requesting code for {PHONE} on VPS...")
    session_path = os.path.join("data", "userbot_session")
    
    # Ensure data directory exists
    if not os.path.exists("data"):
        os.makedirs("data")
        
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        # Request code
        sent_code = await client.send_code_request(PHONE)
        print(f"HASH_RECEIVED: {sent_code.phone_code_hash}")
        print("Please enter the code you received.")
    else:
        print("ALREADY_AUTHORIZED")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
