import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def main():
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    
    if not api_id or not api_hash:
        print("❌ Error: API_ID or API_HASH not found in .env file.")
        return

    print("--- Starting Userbot Login Process ---")
    print(f"Using API_ID: {api_id}")
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    session_path = os.path.join("data", "oisha_user.session")
    
    client = TelegramClient(session_path, int(api_id), api_hash)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        # Using sys.stdout.flush to ensure the prompt is visible
        import sys
        print("INPUT_REQUIRED:PHONE")
        sys.stdout.flush()
        phone = input("Enter your phone number (with +country code): ")
        await client.send_code_request(phone)
        print("INPUT_REQUIRED:CODE")
        sys.stdout.flush()
        code = input("Enter the code you received on Telegram: ")
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "2FA" in str(e) or "password" in str(e).lower():
                print("INPUT_REQUIRED:2FA")
                sys.stdout.flush()
                password = input("Two-factor authentication detected. Enter your password: ")
                await client.sign_in(password=password)
            else:
                raise e
            
    me = await client.get_me()
    print(f"DONE: Successfully logged in as: {me.first_name} (@{me.username})")
    print(f"SESSION_PATH: {session_path}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
