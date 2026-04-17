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

    print("🚀 Starting Userbot Login Process...")
    print(f"Using API_ID: {api_id}")
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    session_path = os.path.join("data", "oisha_user.session")
    
    client = TelegramClient(session_path, int(api_id), api_hash)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        phone = input("📱 Enter your phone number (with +country code): ")
        await client.send_code_request(phone)
        code = input("🔢 Enter the code you received on Telegram: ")
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            password = input("🔐 Two-factor authentication detected. Enter your password: ")
            await client.sign_in(password=password)
            
    me = await client.get_me()
    print(f"✅ Successfully logged in as: {me.first_name} (@{me.username})")
    print(f"📂 Session saved at: {session_path}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
