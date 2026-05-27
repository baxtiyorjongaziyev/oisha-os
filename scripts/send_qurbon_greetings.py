"""Qurbon Hayit tabrigi — Tez natija 2/3/4/5 guruh a'zolariga."""
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

API_ID = 30643078
API_HASH = "***REDACTED***"
SESSION_STRING = os.environ["USERBOT_SESSION_STRING"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = 150074828

TARGET_GROUPS = ["Tez natija 2", "Tez natija 3", "Tez natija 4", "Tez natija 5"]


def build_message(first_name: str) -> str:
    return (
        f"Assalomu alaykum, {first_name}!\n\n"
        "Qurbon hayit muborak bo'lsin \U0001f319\n"
        "Alloh taolo qurboningizni qabul qilsin,\n"
        "oilangizga baraka va sog'lik bersin!\n\n"
        "Hayit tantanali o'tsin \U0001f932"
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
                members.append({
                    "id": user.id,
                    "first_name": (user.first_name or "").strip() or "Do'st",
                    "username": user.username or "",
                })
        except ChatAdminRequiredError:
            print(f"  SKIP {title}: admin huquqi kerak")
        except Exception as e:
            print(f"  SKIP {title}: {e}")

    missing = [g for g in TARGET_GROUPS if not any(f.lower() == g.lower() for f in found_groups)]
    if missing:
        print(f"Topilmagan guruhlar: {missing}")

    return members


async def send_to_member(client: TelegramClient, member: dict) -> None:
    msg = build_message(member["first_name"])
    await client.send_message(member["id"], msg)


async def main() -> None:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("Telethon ulandi — guruhlar skanerlanmoqda...")

    members = await collect_members(client)
    total = len(members)
    print(f"Jami unikal a'zolar: {total}")

    if total == 0:
        send_tg_notification("Qurbon Hayit tabrigi: hech kim topilmadi. Guruh nomlarini tekshiring.")
        await client.disconnect()
        return

    send_tg_notification(
        f"Qurbon Hayit tabrigi boshlandi\n"
        f"{total} kishi ro'yxatda\n"
        f"~{total * 10 // 60} daqiqa ketadi"
    )

    sent = 0
    failed = 0
    failed_names: list[str] = []

    for i, member in enumerate(members):
        label = f"[{i+1}/{total}] {member['first_name']} (id={member['id']})"
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
                failed_names.append(member["first_name"])
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
            failed_names.append(member["first_name"])
            print(f"FAIL {label}: {e}")

        if (i + 1) % 50 == 0:
            send_tg_notification(
                f"Jarayon: {i+1}/{total}\n{sent} yuborildi, {failed} xato"
            )

        await asyncio.sleep(random.uniform(8, 12))

    await client.disconnect()

    summary = (
        f"Qurbon Hayit tabrigi yakunlandi!\n"
        f"Yuborildi: {sent}\n"
        f"Xato: {failed}\n"
        f"Jami: {total}"
    )
    if failed_names:
        top_failed = "\n".join(failed_names[:10])
        summary += f"\n\nXato bo'lganlar:\n{top_failed}"
        if len(failed_names) > 10:
            summary += f"\n... va {len(failed_names) - 10} ta boshqa"

    send_tg_notification(summary)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
