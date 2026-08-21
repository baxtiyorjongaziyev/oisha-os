"""Juma tabrigi — Tez natija 2/3/4/5 guruh a'zolariga DM."""
import asyncio
import contextlib
import os
import random
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

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

#: Ketma-ket shuncha "disconnected" xatosidan keyin broadcast to'xtatiladi —
#: session boshqa jarayon bilan bahslashayotganini bildiradi, qayta-qayta
#: urinish foydasiz (2026-08-21 hodisasi: 94 yuborilgach barchasi shu bilan
#: yiqildi, chunki oisha-os.service o'sha paytda bir xil session'ni tutgan edi).
MAX_CONSECUTIVE_DISCONNECTS = 3

#: Telegram userbot (oddiy foydalanuvchi akkaunti, Bot API emas) ko'pchilikka
#: BIR XIL matnni ketma-ket yuborishni klassik spam signali deb hisoblaydi —
#: bu aynan 2026-08-21 kuni akkauntning BARCHA qurilmalardan chiqarib
#: yuborilishiga olib kelgan xatti-harakat. Xavfsiz qayta ishga tushirish
#: uchun bir martalik yuborishlar soni va oralig'i ataylab konservativ
#: (env orqali moslashtiriladi — akkaunt "ishonchni tiklagach" asta oshiring).
MAX_MESSAGES_PER_RUN = int(os.environ.get("JUMA_MAX_PER_RUN", "50"))
DELAY_MIN_SEC = float(os.environ.get("JUMA_DELAY_MIN_SEC", "20"))
DELAY_MAX_SEC = float(os.environ.get("JUMA_DELAY_MAX_SEC", "35"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.telethon_guard import (  # noqa: E402
    SessionConflictError,
    SessionMissingError,
    guarded_connect,
    guarded_is_authorized,
    prepare,
    single_flight,
)

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
_now_tashkent = datetime.now(TASHKENT_TZ)
if _now_tashkent.weekday() != 4:  # 4 = Juma (Friday)
    day_name = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"][_now_tashkent.weekday()]
    print(f"Bugun {day_name} — Juma kuni emas. Yuborilmadi.")
    sys.exit(0)

print(f"Juma tasdiqlandi: {_now_tashkent.strftime('%Y-%m-%d %H:%M')} Toshkent vaqti")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "150074828"))

# Session tanlash va xavfsizlik tekshiruvi telethon_guard da — prod userbot
# kaliti hech qachon Oracle VM dan tashqarida ochilmasligi kerak.
DEDICATED_SESSION_ENV = "JUMA_SESSION_STRING"

TARGET_GROUPS = [
    "Tez natija 2", "Tez natija 3", "Tez natija 4", "Tez natija 5", "Tez natija 6",
    '"TEZ NATIJA 2" UMUMIY', '"TEZ NATIJA 3" UMUMIY', '"TEZ NATIJA 4" UMUMIY', '"TEZ NATIJA 5" UMUMIY', '"TEZ NATIJA 6" UMUMIY',
    "TN2 Gr", "TN3 Gr", "TN4 Gr", "TN5 Gr", "TN6 Gr",
]
TARGET_GROUP_IDS = [
    int(os.environ.get("TN6_GROUP_ID", "-1003496493814")),
    int(os.environ.get("TN5_GROUP_ID", "-1003820339529")),
    int(os.environ.get("TN4_GROUP_ID", "-1003149184518")),
    int(os.environ.get("TN3_GROUP_ID", "-1002849105320")),
    int(os.environ.get("TN2_GROUP_ID", "-1002440481294")),
]

MESSAGE = (
    "Assalomu alaykum!\n\n"
    "Juma muborak bo’lsin!\n"
    "Bu muborak kunda barcha niyatlaringiz ro‘yobga chiqsin, "
    "rizqingiz mo‘l, umringiz barakali bo’lsin."
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
    found_dialog_ids: set[int] = set()
    all_dialogs = [d async for d in client.iter_dialogs()]

    for dialog in all_dialogs:
        title = (dialog.title or "").strip()
        is_name_match = any(title.lower() == g.lower() for g in TARGET_GROUPS)
        is_id_match = dialog.id in TARGET_GROUP_IDS
        if not (is_name_match or is_id_match):
            continue
        found_dialog_ids.add(dialog.id)
        found_groups.append(f"{title} ({dialog.id})")
        print(f"Guruh topildi: {title} (ID: {dialog.id})")
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

    missing_ids = [gid for gid in TARGET_GROUP_IDS if gid not in found_dialog_ids]
    if missing_ids:
        msg = f"OGOHLANTIRISH: {len(missing_ids)} guruh topilmadi (ID: {missing_ids})"
        print(msg)
        send_tg_notification(msg)

    return members


async def send_to_member(client: TelegramClient, member: dict) -> None:
    await client.send_message(member["id"], MESSAGE)


async def run() -> None:
    send_tg_notification("⚙️ Juma tabrigi workflow ishga tushdi — Telethon ulanmoqda...")
    source = prepare(DEDICATED_SESSION_ENV)
    client = TelegramClient(StringSession(source.string), API_ID, API_HASH)
    try:
        await guarded_connect(client, source)
        if not await guarded_is_authorized(client, source):
            send_tg_notification(
                f"❌ Session muddati tugagan yoki noto'g'ri ({source.origin}). "
                "Yangi session kerak."
            )
            await client.disconnect()
            return
    except SessionConflictError:
        # Xabar main() da yuboriladi — bu yerda faqat ulanishni yopamiz.
        with contextlib.suppress(Exception):
            await client.disconnect()
        raise
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

    run_target = min(total, MAX_MESSAGES_PER_RUN)
    avg_delay = (DELAY_MIN_SEC + DELAY_MAX_SEC) / 2
    send_tg_notification(
        f"Juma tabrigi boshlandi\n"
        f"{total} kishi roʻyxatda, bu safar {run_target} tasiga yuboriladi "
        f"(Telegram xavfsizligi uchun bir martalik limit: {MAX_MESSAGES_PER_RUN})\n"
        f"~{int(run_target * avg_delay // 60)} daqiqa ketadi"
    )

    sent = 0
    failed = 0
    consecutive_disconnects = 0
    aborted_reason = None
    hit_run_cap = False

    def _is_disconnected(exc: BaseException) -> bool:
        return isinstance(exc, ConnectionError) or "disconnected" in str(exc).lower()

    try:
        for i, member in enumerate(members):
            label = f"[{i+1}/{total}] id={member['id']}"
            try:
                await send_to_member(client, member)
                sent += 1
                consecutive_disconnects = 0
                print(f"OK {label}")
            except PeerFloodError as e:
                # Telegram bu yerda "juda ko'p odamga yozyapsiz" deb hisobladi —
                # davom etish faqat cheklovni uzaytiradi. Darhol to'xtaymiz.
                aborted_reason = (
                    "🛑 Juma tabrigi TO'XTATILDI: PeerFloodError\n\n"
                    "Telegram ushbu akkauntni ommaviy DM uchun cheklab qo'ydi. "
                    "Davom etish cheklovni uzaytiradi — akkaunt bir necha soat/kun "
                    "tinch turishi kerak, keyin qayta urinib ko'ring.\n\n"
                    f"To'xtagan joy: {label}\n"
                    f"Shu paytgacha: {sent} yuborildi, {failed} xato"
                )
                print(aborted_reason)
                break
            except FloodWaitError as e:
                wait_sec = e.seconds + 5
                print(f"FloodWait {wait_sec}s — {label}")
                await asyncio.sleep(wait_sec)
                try:
                    await send_to_member(client, member)
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
                if _is_disconnected(e):
                    consecutive_disconnects += 1
                    print(
                        f"DISCONNECTED ({consecutive_disconnects}/"
                        f"{MAX_CONSECUTIVE_DISCONNECTS}) {label}: {e}"
                    )
                    with contextlib.suppress(Exception):
                        await client.connect()
                    if consecutive_disconnects >= MAX_CONSECUTIVE_DISCONNECTS:
                        aborted_reason = (
                            "🛑 Juma tabrigi TO'XTATILDI: ulanish uzilishi "
                            f"({consecutive_disconnects} marta ketma-ket)\n\n"
                            "Odatda sababi: boshqa jarayon (masalan "
                            "oisha-os.service) bir xil session'ni ayni paytda "
                            "ushlab turibdi. Qayta urinish foydasiz — avval "
                            f"{DEDICATED_SESSION_ENV} ga alohida session "
                            "qo'yib qayta ishga tushiring.\n\n"
                            f"To'xtagan joy: {label}\n"
                            f"Shu paytgacha: {sent} yuborildi, {failed} xato"
                        )
                        failed += 1
                        print(aborted_reason)
                        break
                    failed += 1
                    print(f"FAIL {label}: {e}")
                    continue
                failed += 1
                consecutive_disconnects = 0
                print(f"FAIL {label}: {e}")

            if (i + 1) % 50 == 0:
                send_tg_notification(
                    f"Jarayon: {i+1}/{total}\n{sent} yuborildi, {failed} xato"
                )

            if sent >= MAX_MESSAGES_PER_RUN:
                hit_run_cap = True
                print(
                    f"LIMIT: bir martalik {MAX_MESSAGES_PER_RUN} yuborish "
                    f"chegarasiga yetdi — Telegram xavfsizligi uchun to'xtatildi."
                )
                break

            await asyncio.sleep(random.uniform(DELAY_MIN_SEC, DELAY_MAX_SEC))

        if hit_run_cap:
            # DIQQAT: skript hozircha kimga allaqachon yuborilganini saqlamaydi —
            # keyingi ishga tushirishda ro'yxat BOSHIDAN qayta boshlanadi. Demak
            # {total - MAX_MESSAGES_PER_RUN} kishi bu limit turgan ekan hech
            # qachon tabrik olmaydi, faqat JUMA_MAX_PER_RUN oshirilmasa yoki
            # davomiylik (cursor) logikasi qo'shilmasa.
            send_tg_notification(
                "⏸ Juma tabrigi bir martalik limitga yetdi va TO'XTATILDI "
                f"(Telegram xavfsizligi uchun ataylab: {MAX_MESSAGES_PER_RUN} ta).\n\n"
                f"Yuborildi: {sent}/{total}\n"
                "DIQQAT: skript kimga yuborilganini eslab qolmaydi — keyingi safar "
                "ro'yxat boshidan boshlanadi. Qolgan "
                f"{total - sent} kishi tabrik olishi uchun JUMA_MAX_PER_RUN ni "
                "oshiring yoki avval navbat (cursor) logikasini qo'shishni so'rang."
            )
        if aborted_reason:
            send_tg_notification(aborted_reason)
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


async def main() -> None:
    """Bitta hostda faqat bitta userbot skripti ulansin (single-flight)."""
    try:
        with single_flight("userbot_oneoff"):
            await run()
    except (SessionConflictError, SessionMissingError) as exc:
        print(f"TO'XTATILDI: {exc}")
        send_tg_notification(f"⛔️ Juma tabrigi to'xtatildi\n\n{exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
