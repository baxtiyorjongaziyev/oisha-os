"""
Yangi USERBOT_SESSION_STRING yaratish.
Lokal kompyuterda bir marta ishga tushiring:

  pip install telethon python-dotenv
  export API_ID=... API_HASH=...   # https://my.telegram.org
  python scripts/generate_session_string.py

Natijada chiqadigan SESSION_STRING qiymatini
GitHub Secrets → USERBOT_SESSION_STRING ga joylashtiring.
"""
import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]


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
