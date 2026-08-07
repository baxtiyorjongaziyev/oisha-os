"""Bugungi Juma tabrigi xabarlarini o'chiradi (userbot tomonidan yuborilgan DM'lar).

Xavfsizlik: faqat bugun yuborilgan va mos matn bo'lgan xabarlarni o'chiradi.
"""
import asyncio
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.telethon_guard import (  # noqa: E402
    SessionConflictError,
    SessionMissingError,
    guarded_connect,
    guarded_is_authorized,
    prepare,
    single_flight,
)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "150074828"))

# Session tanlash va xavfsizlik tekshiruvi telethon_guard da — prod userbot
# kaliti hech qachon Oracle VM dan tashqarida ochilmasligi kerak.
DEDICATED_SESSION_ENV = "JUMA_SESSION_STRING"

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


async def run() -> None:
    notify("🗑 Juma xabarlarini o'chirish boshlandi...")
    source = prepare(DEDICATED_SESSION_ENV)
    client = TelegramClient(StringSession(source.string), API_ID, API_HASH)
    await guarded_connect(client, source)

    if not await guarded_is_authorized(client, source):
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


async def main() -> None:
    """Bitta hostda faqat bitta userbot skripti ulansin (single-flight)."""
    try:
        with single_flight("userbot_oneoff"):
            await run()
    except (SessionConflictError, SessionMissingError) as exc:
        print(f"TO'XTATILDI: {exc}")
        notify(f"⛔️ Juma xabarlarini o'chirish to'xtatildi\n\n{exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
