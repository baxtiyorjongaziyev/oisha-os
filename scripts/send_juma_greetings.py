"""Juma tabrigi — Tez natija 2/3/4/5 guruh a'zolariga DM."""
import asyncio
import os
import random
import urllib.parse
import urllib.request

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    InputUserDeactivatedError,
    PeerIdInvalidError,
    UserNotMutualContactError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)

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

TARGET_GROUPS = ["Tez natija 2", "Tez natija 3", "Tez natija 4", "Tez natija 5"]

MESSAGE = (
    "Assalomu alaykum \U0001f44b\n\n"
    "Juma muborak bo’lsin! \U0001f319\n"
    "Bu muborak kunda barcha niyatlaringiz ro‘yobga chiqsin,\n"
    "rizqingiz mo‘l, umringiz barakali bo’lsin. \U0001f932\n\n"
    "— Jon Branding Academy"
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


async def collect_members(client: TelegramClient) -> list[dict]:
    seen_ids: set[int] = set()
    members: list[dict] = []
    found_groups: list[str] = []

    async for dialog in client.iter_dialogs():
        title = (dialog.title or "").strip()
        if not any(title.lower() == g.lower() for g in TARGET_GROUPS):
            continue
        found_groups.append(title)
        print(f"Guruh topildi: {title}")
        try:
            async for user in client.iter_participants(dialog):
                if user.bot or user.deleted or user.id in seen_ids:
                    continue
                seen_ids.add(user.id)
                members.append({"id": user.id})
        except ChatAdminRequiredError:
            print(f"  SKIP {title}: admin huquqi kerak")
        except Exception as e:
            print(f"  SKIP {title}: {e}")

    missing = [g for g in TARGET_GROUPS if not any(f.lower() == g.lower() for f in found_groups)]
    if missing:
        msg = f"OGOHLANTIRISH: {len(missing)} guruh topilmadi: {missing}"
        print(msg)
        send_tg_notification(msg)

    return members


async def send_to_member(client: TelegramClient, member: dict) -> None:
    await client.send_message(member["id"], MESSAGE)


async def main() -> None:
    send_tg_notification("⚙️ Juma tabrigi workflow ishga tushdi — Telethon ulanmoqda...")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            send_tg_notification(
                "❌ Session muddati tugagan yoki notoʻgʻri. "
                "Yangi USERBOT_SESSION_STRING kerak."
            )
            await client.disconnect()
            return
    except Exception as e:
        send_tg_notification(f"❌ Telethon ulana olmadi: {e}")
        raise
    print("Telethon ulandi — guruhlar skanerlanmoqda...")
    send_tg_notification("✅ Telethon ulandi — guruhlar skanerlanmoqda...")

    members = await collect_members(client)
    total = len(members)
    print(f"Jami unikal aʼzolar: {total}")

    if total == 0:
        send_tg_notification(
            "Juma tabrigi: hech kim topilmadi. Guruh nomlarini tekshiring."
        )
        await client.disconnect()
        return

    send_tg_notification(
        f"Juma tabrigi boshlandi\n"
        f"{total} kishi roʻyxatda\n"
        f"~{total * 10 // 60} daqiqa ketadi"
    )

    sent = 0
    failed = 0

    try:
        for i, member in enumerate(members):
            label = f"[{i+1}/{total}] id={member['id']}"
            try:
                await send_to_member(client, member)
                sent += 1
                print(f"OK {label}")
            except FloodWaitError as e:
                wait_sec = e.seconds + 5
                print(f"FloodWait {wait_sec}s — {label}")
                await asyncio.sleep(wait_sec)
                try:
                    await send_to_member(client, member)
                    sent += 1
                    print(f"OK (retry) {label}")
                except Exception as retry_err:
                    failed += 1
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
    send_tg_notification(summary)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
