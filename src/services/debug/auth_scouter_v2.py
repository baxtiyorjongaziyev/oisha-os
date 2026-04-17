
import os
import asyncio
import time
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "userbot_session"
PHONE = "+998336450097"
CODE_FILE = "code.txt"

async def main():
    if not API_ID or not API_HASH:
        print("Error: API_ID or API_HASH missing in .env")
        return

    client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
    print("Connecting to Telegram...")
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Sending code request to {PHONE}...")
        await client.send_code_request(PHONE)
        
        print(f"Waiting for {CODE_FILE} to appear...")
        # Wait up to 5 minutes for the file
        start_time = time.time()
        while time.time() - start_time < 300:
            if os.path.exists(CODE_FILE):
                with open(CODE_FILE, "r") as f:
                    code = f.read().strip()
                if code:
                    print(f"Found code: {code}. Attempting sign in...")
                    try:
                        await client.sign_in(PHONE, code)
                        os.remove(CODE_FILE) # Clean up
                        print("Successfully signed in!")
                        break
                    except Exception as e:
                        print(f"Sign in error: {e}")
                        return
            await asyncio.sleep(5)
        else:
            print("Timed out waiting for code.txt")
            return

    me = await client.get_me()
    print(f"Successfully authorized as: {me.first_name} (@{me.username})")
    print(f"Session saved to {SESSION_NAME}.session")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
