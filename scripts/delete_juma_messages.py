"""Bugungi Juma tabrigi xabarlarini o'chiradi (userbot tomonidan yuborilgan DM'lar).

Xavfsizlik: faqat bugun yuborilgan va mos matn bo'lgan xabarlarni o'chiradi.
"""
import asyncio
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "150074828"))

SESSION_STRING = os.environ.get("USERBOT_SESSION_STRING", "")
_session_file = "data/session_output.txt"
try:
    if os.path.exists(_session_file):
        _file_session = open(_session_file).read().strip()
        if _file_session:
            SESSION_STRING = _file_session
except Exception:
    pass

# Juma tabrigi matni — faqat shu matn bo'lgan xabarlar o'chiriladi
GREETING_SNIPPET = "Juma muborak bo'lsin"

# Bugunning boshi (UTC)
TODAY_START = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)


def notify(text: str) -> None:
    if not BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": OWNER_ID, "text": text}).encode()
        with urllib.request.urlopen(url, data=data, timeout=10):
            pass
    except Exception as e:
        print(f"Notification failed: {e}")


async def main() -> None:
    notify("🗑 Juma xabarlarini o'chirish boshlandi...")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        notify("❌ Session eskirgan — o'chirish mumkin emas.")
        await client.disconnect()
        return

    deleted_chats = 0
    deleted_msgs = 0

    async for dialog in client.iter_dialogs():
        # Faqat shaxsiy chatlar (user)
        if not dialog.is_user:
            continue

        to_delete = []
        async for msg in client.iter_messages(dialog, limit=20, from_user="me"):
            if msg.date is None:
                continue
            msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
            if msg_date < TODAY_START:
                break  # Bugundan oldingi — to'xtat
            if GREETING_SNIPPET in (msg.text or ""):
                to_delete.append(msg.id)

        if to_delete:
            try:
                await client.delete_messages(dialog, to_delete, revoke=True)
                deleted_msgs += len(to_delete)
                deleted_chats += 1
                print(f"O'chirildi: {dialog.name} — {len(to_delete)} ta xabar")
            except Exception as e:
                print(f"XATO {dialog.name}: {e}")

        await asyncio.sleep(0.3)

    summary = (
        f"✅ O'chirish yakunlandi!\n"
        f"Chat: {deleted_chats}\n"
        f"Xabar: {deleted_msgs} ta o'chirildi"
    )
    notify(summary)
    print(summary)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
