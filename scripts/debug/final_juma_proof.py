import asyncio
import os
import sys
from telethon import TelegramClient

# HARDCODED for one-off test
API_ID = 30643078
API_HASH = 'e5850001c1d86ac0fb439fbd8319cb7f'
OWNER_ID = 150074828

async def final_proof():
    session_path = 'data/bot_session'
    if not os.path.exists(f"{session_path}.session"):
        print(f"❌ Session file {session_path}.session missing!")
        return

    print(f"🚀 Attempting final proof with {session_path}...")
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ UNAUTHORIZED! We found the file but it's not logged in.")
            return

        msg = "👸 [GOD MODE TEST] Assalomu alaykum! Jumaning xayru barokati sizga bo'lsin! 🕌✨"
        sent = await client.send_message(OWNER_ID, msg)
        print(f"✅ SUCCESS! Message sent. ID: {sent.id}")
        print(f"👸 Xabar yuborildi! Iltimos, Telegramingizni ({OWNER_ID}) tekshiring.")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(final_proof())
