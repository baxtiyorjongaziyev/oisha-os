"""
Telegram MCP uchun ALOHIDA session yaratish (Oracle userbot'ga tegmaydi).
Lokal kompyuterda ishga tushiring:

  export API_ID=... API_HASH=...   # https://my.telegram.org
  python scripts/generate_mcp_session_local.py +998XXXXXXXXX

Natijada chiqadigan session_string qiymatini Oracle .env fayliga
TELEGRAM_MCP_SESSION_STRING sifatida qo'shing (owner tomonidan).
"""
import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]


async def main() -> None:
    if len(sys.argv) < 2:
        print("Foydalanish: python generate_mcp_session_local.py +998XXXXXXXXX")
        return

    phone = sys.argv[1]

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start(phone=phone)
    try:
        me = await client.get_me()
        session_str = client.session.save()
    finally:
        await client.disconnect()

    print("\n" + "=" * 60)
    print("Login muvaffaqiyatli:", me.first_name, f"(@{me.username})")
    print("=" * 60)
    print("\nBu qiymatni Oracle .env -> TELEGRAM_MCP_SESSION_STRING ga qo'ying:\n")
    print(session_str)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
