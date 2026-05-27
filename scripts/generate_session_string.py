"""
Yangi USERBOT_SESSION_STRING yaratish.
Lokal kompyuterda bir marta ishga tushiring:

  pip install telethon python-dotenv
  python scripts/generate_session_string.py

Natijada chiqadigan SESSION_STRING qiymatini
GitHub Secrets → USERBOT_SESSION_STRING ga joylashtiring.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID   = 30643078
API_HASH = "***REDACTED***"


async def main() -> None:
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start()
        me = await client.get_me()
        session_str = client.session.save()

    print("\n" + "=" * 60)
    print("✅ Login muvaffaqiyatli:", me.first_name, f"(@{me.username})")
    print("=" * 60)
    print("\nQuyidagi qiymatni GitHub Secrets → USERBOT_SESSION_STRING ga joylashtiring:\n")
    print(session_str)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
