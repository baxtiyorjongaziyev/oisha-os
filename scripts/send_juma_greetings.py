"""Juma tabrigi — TN5 kursdoshlarga massa xabar yuborish."""
import asyncio
import csv
import os
import random
import urllib.parse
import urllib.request

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    UserNotMutualContactError,
    InputUserDeactivatedError,
    PeerIdInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["USERBOT_SESSION_STRING"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "150074828"))

MESSAGE = (
    "Assalomu alaykum\n"
    "Juma ayyomingiz muborak bo'lsin.\n"
    "Jumaning xayru barokati sizga bo'lsin."
)


def send_tg_notification(text: str) -> None:
    if not BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": OWNER_ID, "text": text}).encode()
        with urllib.request.urlopen(url, data=data, timeout=10):
            pass
    except Exception as e:
        print(f"Notification failed: {e}")


def load_contacts(csv_path: str) -> list:
    contacts = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "")
            if "TN5" not in name:
                continue
            username = row.get("username", "").strip().lstrip("@")
            user_id = row.get("user_id", "").strip()
            if username or user_id:
                contacts.append({
                    "name": name[:40],
                    "username": username,
                    "user_id": user_id,
                })
    return contacts


async def send_to_contact(client, contact: dict) -> None:
    if contact["username"]:
        target = contact["username"]
    else:
        target = int(contact["user_id"])
    await client.send_message(target, MESSAGE)


async def main() -> None:
    contacts = load_contacts("data/juma_outreach_list.csv")
    total = len(contacts)
    print(f"Topildi: {total} ta TN5 kursdosh")

    send_tg_notification(
        f"Juma tabrigi boshlandi\n"
        f"{total} kishi royxatda\n"
        f"~{total * 10 // 60} daqiqa ketadi"
    )

    send_tg_notification("⚙️ Juma tabrigi ishga tushdi — Telethon ulanmoqda...")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            send_tg_notification("❌ Session muddati tugagan yoki noto'g'ri. Yangi USERBOT_SESSION_STRING kerak.")
            await client.disconnect()
            return
    except Exception as e:
        send_tg_notification(f"❌ Telethon ulana olmadi: {e}")
        raise
    print("Telethon ulandi")
    send_tg_notification("✅ Telethon ulandi — xabarlar yuborilmoqda...")

    sent = 0
    failed = 0
    failed_names: list = []

    try:
        for i, contact in enumerate(contacts):
            label = f"[{i+1}/{total}] {contact['name']}"
            try:
                await send_to_contact(client, contact)
                sent += 1
                print(f"OK {label}")
            except FloodWaitError as e:
                wait_sec = e.seconds + 5
                print(f"FloodWait {wait_sec}s - {label}")
                await asyncio.sleep(wait_sec)
                try:
                    await send_to_contact(client, contact)
                    sent += 1
                    print(f"OK (retry) {label}")
                except Exception as retry_err:
                    failed += 1
                    failed_names.append(contact["name"])
                    print(f"FAIL (retry) {label}: {retry_err}")
                continue
            except (
                UserNotMutualContactError,
                InputUserDeactivatedError,
                PeerIdInvalidError,
                UsernameNotOccupiedError,
                UsernameInvalidError,
            ) as e:
                failed += 1
                print(f"SKIP {label}: {type(e).__name__}")
            except Exception as e:
                failed += 1
                failed_names.append(contact["name"])
                print(f"FAIL {label}: {e}")

            if (i + 1) % 50 == 0:
                send_tg_notification(
                    f"Jarayon: {i+1}/{total}\n{sent} yuborildi, {failed} xato"
                )

            await asyncio.sleep(random.uniform(8, 12))
    finally:
        await client.disconnect()

    summary = (
        f"Juma tabrigi yakunlandi!\n"
        f"Yuborildi: {sent}\n"
        f"Xato: {failed}\n"
        f"Jami: {total}"
    )
    if failed_names:
        top_failed = "\n".join(failed_names[:10])
        summary += f"\n\nXato bolganlari:\n{top_failed}"
        if len(failed_names) > 10:
            summary += f"\n... va {len(failed_names) - 10} ta boshqa"

    send_tg_notification(summary)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
