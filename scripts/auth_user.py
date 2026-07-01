"""
Telethon User Auth Script
1. Bu scriptni lokal kompyuteringizda ishga tushiring
2. Telefon raqamingizni kiriting
3. Telegram dan kelgan kodni kiriting
4. Session string chiqadi — uni VPS ga ko'chiring
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")

async def main():
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    print("=== Telethon User Auth ===")
    print("Telefon raqamingizni kiriting (masalan: +998901234567)")
    phone = input("Phone: ")

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start(phone=phone)

    session_string = client.session.save()
    print("\n" + "=" * 50)
    print("SESSION STRING (VPS ga ko'chiring):")
    print("=" * 50)
    print(session_string)
    print("=" * 50)

    # Also save to file
    with open("session_string.txt", "w") as f:
        f.write(session_string)
    print("\nsession_string.txt ga saqlandi.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
