import asyncio
import os
import sys
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

async def test_external(target):
    session_path = 'data/bot_session'
    if not os.path.exists(f"{session_path}.session"):
        print(f"❌ Session file {session_path}.session missing!")
        return

    print(f"🚀 Userbot identity test: Sending to '{target}' using {session_path}...")
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ UNAUTHORIZED!")
            return

        # The exact message the user specified
        msg = "Assalomu alaykum Juma Ayyomgiz muborak bo'lsin. Jumaning xayru barokati sizga bo'lsin! 🕌✨"
        
        sent = await client.send_message(target, msg)
        print(f"✅ SUCCESS! Sent through your personal account. ID: {sent.id}")
        print(f"👸 Xabar '{target}' ga yuborildi! Yuborilgan xabarlaringizda ko'rishingiz mumkin.")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_juma_external.py <username_or_id>")
    else:
        asyncio.run(test_external(sys.argv[1]))
