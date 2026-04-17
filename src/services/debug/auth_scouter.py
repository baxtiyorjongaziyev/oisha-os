
import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "userbot_session"

async def main():
    if not API_ID or not API_HASH:
        print("Error: API_ID or API_HASH missing in .env")
        return

    client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
    
    print("Connecting to Telegram...")
    await client.connect()
    
    if not await client.is_user_authorized():
        phone = input("Please enter your phone number (with country code): ")
        try:
            await client.send_code_request(phone)
            code = input("Please enter the code you received: ")
            await client.sign_in(phone, code)
        except Exception as e:
            if '2FA' in str(e) or 'password' in str(e).lower():
                password = input("Please enter your 2FA password: ")
                await client.sign_in(password=password)
            else:
                print(f"Error: {e}")
                return
                
    me = await client.get_me()
    print(f"Successfully authorized as: {me.first_name} (@{me.username})")
    print(f"Session saved to {SESSION_NAME}.session")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
