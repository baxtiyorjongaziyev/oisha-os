"""Bir martalik Juma tabrigi — kun tekshiruvsiz, faqat TN6 a'zolariga.

Ishlatish:
  # Faqat test (bitta kishi):
  python scripts/send_juma_oneoff.py --test-user BoymatovJurabek

  # TN6 ga to'liq broadcast:
  python scripts/send_juma_oneoff.py --broadcast
"""
import argparse
import asyncio
import contextlib
import os
import random
import sys
import urllib.parse
import urllib.request

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    InputUserDeactivatedError,
    PeerFloodError,
    PeerIdInvalidError,
    UserNotMutualContactError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.telethon_guard import (  # noqa: E402
    SessionConflictError,
    SessionMissingError,
    guarded_connect,
    guarded_is_authorized,
    prepare,
    single_flight,
)

DELAY_MIN_SEC = float(os.environ.get("JUMA_DELAY_MIN_SEC", "20"))
DELAY_MAX_SEC = float(os.environ.get("JUMA_DELAY_MAX_SEC", "35"))
MAX_CONSECUTIVE_DISCONNECTS = 3

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "150074828"))

DEDICATED_SESSION_ENV = "JUMA_SESSION_STRING"

TN6_GROUP_ID = int(os.environ.get("TN6_GROUP_ID", "-1003496493814"))
TN6_NAMES = {"tez natija 6", '"tez natija 6" umumiy', "tn6 gr"}

JUMA_TEMPLATES = [
    (
        "Assalomu alaykum! Juma muborak bo'lsin \U0001f932\n\n"
        "Alloh xonadoningizga baraka, ishlaringizga rivoj bersin. "
        "Bugungi qilgan duolaringiz qabul bo'lib, ko'nglingiz doim xotirjam bo'lsin."
    ),
    (
        "Assalomu alaykum! Juma muborak bo'lsin! \U0001f932\n\n"
        "Alloh kuningizni xayrli, ishlaringizni barakali qilsin. "
        "Yaxshi niyatlaringizga yetkazsin."
    ),
    (
        "Assalomu alaykum! Juma muborak bo'lsin! \U0001f932\n\n"
        "Alloh rizqingizga baraka bersin, ko'nglingizni xotirjam qilsin. "
        "Niyat qilgan yaxshi ishlaringizga yetkazib, duolaringizni qabul qilsin."
    ),
]


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


async def send_test(client: TelegramClient, username: str) -> None:
    """Bitta odamga test xabar yuborish."""
    text = random.choice(JUMA_TEMPLATES)
    print(f"Test xabar yuborilmoqda: @{username}")
    print(f"Matn:\n{text}\n")
    await client.send_message(username, text)
    print(f"OK — @{username} ga yuborildi!")
    notify(f"Test Juma tabrigi @{username} ga muvaffaqiyatli yuborildi!")


async def collect_tn6_members(client: TelegramClient) -> list[dict]:
    """Faqat TN6 guruhidan a'zolarni yig'adi."""
    members: list[dict] = []
    all_dialogs = [d async for d in client.iter_dialogs()]
    matching = [
        d for d in all_dialogs
        if d.id == TN6_GROUP_ID or (d.title or "").strip().lower() in TN6_NAMES
    ]
    if not matching:
        print(f"XATO: Tez Natija 6 guruhi topilmadi (ID: {TN6_GROUP_ID})")
        notify("XATO: Tez Natija 6 guruhi topilmadi")
        return members

    for dialog in matching:
        title = (dialog.title or "").strip()
        print(f"Guruh topildi: {title} (ID: {dialog.id})")
        try:
            async for user in client.iter_participants(dialog):
                if user.bot or user.deleted:
                    continue
                members.append({"id": user.id, "name": f"{user.first_name or ''} {user.last_name or ''}".strip()})
        except ChatAdminRequiredError:
            print(f"  SKIP {title}: admin huquqi kerak")
        except Exception as e:
            print(f"  SKIP {title}: {e}")

    # Dublikatlarni olib tashlash
    seen = set()
    unique = []
    for m in members:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    return unique


async def broadcast_tn6(client: TelegramClient) -> None:
    """TN6 a'zolariga 20-35s pauzali broadcast."""
    members = await collect_tn6_members(client)
    total = len(members)
    print(f"TN6 dan {total} ta a'zo topildi")

    if total == 0:
        notify("Juma tabrigi: TN6 dan hech kim topilmadi.")
        return

    notify(
        f"Juma tabrigi TN6 broadcast boshlandi\n"
        f"{total} kishi ro'yxatda\n"
        f"~{int(total * (DELAY_MIN_SEC + DELAY_MAX_SEC) / 2 / 60)} daqiqa ketadi"
    )

    sent = 0
    failed = 0
    consecutive_disconnects = 0

    for i, member in enumerate(members):
        label = f"[{i+1}/{total}] id={member['id']} ({member['name']})"
        text = random.choice(JUMA_TEMPLATES)
        try:
            await client.send_message(member["id"], text)
            sent += 1
            consecutive_disconnects = 0
            print(f"OK {label}")
        except PeerFloodError:
            notify(
                f"🛑 PeerFloodError — broadcast TO'XTATILDI\n"
                f"Yuborildi: {sent}, Xato: {failed}, Jami: {total}"
            )
            print(f"PeerFloodError — to'xtatildi {label}")
            break
        except FloodWaitError as e:
            wait_sec = e.seconds + 5
            print(f"FloodWait {wait_sec}s — {label}")
            await asyncio.sleep(wait_sec)
            try:
                await client.send_message(member["id"], text)
                sent += 1
                consecutive_disconnects = 0
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
            consecutive_disconnects = 0
            print(f"SKIP {label}: {type(e).__name__}")
        except Exception as e:
            if "disconnected" in str(e).lower() or isinstance(e, ConnectionError):
                consecutive_disconnects += 1
                print(f"DISCONNECTED ({consecutive_disconnects}/{MAX_CONSECUTIVE_DISCONNECTS}) {label}")
                with contextlib.suppress(Exception):
                    await client.connect()
                if consecutive_disconnects >= MAX_CONSECUTIVE_DISCONNECTS:
                    notify(
                        f"🛑 Ulanish uzildi {consecutive_disconnects} marta — TO'XTATILDI\n"
                        f"Yuborildi: {sent}, Xato: {failed}"
                    )
                    break
                failed += 1
                continue
            failed += 1
            consecutive_disconnects = 0
            print(f"FAIL {label}: {e}")

        if (i + 1) % 25 == 0:
            notify(f"Jarayon: {i+1}/{total}\n{sent} yuborildi, {failed} xato")

        await asyncio.sleep(random.uniform(DELAY_MIN_SEC, DELAY_MAX_SEC))

    summary = (
        f"Juma tabrigi TN6 yakunlandi!\n"
        f"Yuborildi: {sent}\n"
        f"Xato: {failed}\n"
        f"Jami: {total}"
    )
    notify(summary)
    print(summary)


async def run(args: argparse.Namespace) -> None:
    notify("⚙️ Juma oneoff skripti ishga tushdi...")
    source = prepare(DEDICATED_SESSION_ENV)
    client = TelegramClient(StringSession(source.string), API_ID, API_HASH)
    try:
        await guarded_connect(client, source)
        if not await guarded_is_authorized(client, source):
            notify(f"❌ Session muddati tugagan ({source.origin})")
            await client.disconnect()
            return
    except SessionConflictError:
        with contextlib.suppress(Exception):
            await client.disconnect()
        raise
    except Exception as e:
        notify(f"❌ Telethon ulana olmadi: {e}")
        raise

    print("Telethon ulandi!")

    try:
        if args.test_user:
            await send_test(client, args.test_user)
        elif args.broadcast:
            await broadcast_tn6(client)
        else:
            print("Hech narsa tanlanmadi. --test-user yoki --broadcast ishlating.")
    finally:
        await client.disconnect()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bir martalik Juma tabrigi (TN6)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test-user", type=str, help="Test xabar yuborish uchun username")
    group.add_argument("--broadcast", action="store_true", help="TN6 ga to'liq broadcast")
    args = parser.parse_args()

    try:
        with single_flight("userbot_oneoff"):
            await run(args)
    except (SessionConflictError, SessionMissingError) as exc:
        print(f"TO'XTATILDI: {exc}")
        notify(f"⛔️ Juma oneoff to'xtatildi\n\n{exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
