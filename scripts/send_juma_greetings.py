"""Juma tabrigi — Tez Natija 7 (va boshqa guruhlar) aʼzolariga xavfsiz DM."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import random
import sys
import urllib.parse
import urllib.request
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError, FloodWaitError, InputUserDeactivatedError,
    PeerFloodError, PeerIdInvalidError, UserNotMutualContactError,
    UserPrivacyRestrictedError, UsernameInvalidError, UsernameNotOccupiedError,
)
from telethon.sessions import StringSession

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.telethon_guard import (  # noqa: E402
    SessionConflictError, SessionMissingError, guarded_connect,
    guarded_is_authorized, prepare, single_flight,
)
from src.services.core.juma_guard import (  # noqa: E402
    JUMA_TEMPLATES, TASHKENT_TZ, JumaRateConfig, classify_and_order_recipients,
    compute_juma_deadline, estimate_duration_minutes, is_excluded_member,
    is_juma_send_window, is_quiet_hours, is_silent_send_time, load_custom_greetings,
    load_juma_rate_config, next_delay_seconds, pick_greeting_text,
    seconds_until_quiet_ends, select_target_groups,
)

MAX_CONSECUTIVE_DISCONNECTS = 3
DEDICATED_SESSION_ENV = "JUMA_SESSION_STRING"
JUMA_KEYWORDS = ("juma muborak", "juma ayyom", "jumaning")
SENT_LOG_DIR = ROOT_DIR / "data" / "juma_sent"


def send_tg_notification(text: str) -> None:
    """Owner Telegramiga qisqa holat xabarini yuboradi."""
    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    owner_id = int(os.environ.get("OWNER_ID", "150074828"))
    if not bot_token:
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": owner_id, "text": text}).encode()
        with urllib.request.urlopen(url, data=data, timeout=10):
            pass
    except Exception as exc:
        print(f"Notification failed: {exc}")


def load_already_sent(log_path: Path) -> set[int]:
    """Shu Juma haftasida yuborilgan user ID larni oʻqiydi."""
    if not log_path.exists():
        return set()
    try:
        return set(json.loads(log_path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"OGOHLANTIRISH: sent-log oʻqilmadi ({exc}) — boʻsh deb hisoblanadi")
        return set()

def mark_sent(user_id: int, already_sent: set[int], log_path: Path) -> None:
    """Yuborilgan user ID ni haftalik sent-log fayliga muhrlaydi."""
    already_sent.add(user_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(sorted(already_sent)), encoding="utf-8")

async def _scan_dialog(
    client: TelegramClient, dialog, group_label: str,
    seen_ids: set[int], existing_dm_ids: set[int], config: JumaRateConfig,
) -> tuple[list[dict], int]:
    rows, excluded_blocked = [], 0
    title = (dialog.title or "").strip()
    print(f"Guruh topildi [{group_label}]: {title} (ID: {dialog.id})")
    try:
        async for user in client.iter_participants(dialog):
            if user.bot or user.deleted or getattr(user, "is_self", False) or user.id in seen_ids:
                continue
            seen_ids.add(user.id)
            uname = getattr(user, "username", None) or ""
            full_name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
            if is_excluded_member({"id": user.id, "username": uname, "name": full_name}, config)[0]:
                excluded_blocked += 1
                continue
            mutual = bool(getattr(user, "mutual_contact", False))
            has_dm = user.id in existing_dm_ids
            rows.append({
                "id": user.id, "username": uname, "name": full_name, "group": group_label,
                "mutual": mutual, "warm": mutual or has_dm, "has_dm": has_dm,
            })
    except ChatAdminRequiredError:
        print(f"  SKIP {title}: admin huquqi kerak")
    except Exception as exc:
        print(f"  SKIP {title}: {exc}")
    return rows, excluded_blocked

async def collect_members(
    client: TelegramClient, target_groups: list[dict], config: JumaRateConfig
) -> tuple[list[dict], dict]:
    """Maqsad guruhlardan unikal aʼzolarni yigʻadi va bloklangan aʼzolarni chiqaradi."""
    all_dialogs = [d async for d in client.iter_dialogs()]
    existing_dm_ids = {d.entity.id for d in all_dialogs if d.is_user and getattr(d, "entity", None)}
    seen_ids: set[int] = set()
    members: list[dict] = []
    excluded_blocked = 0
    for group in target_groups:
        names_low = {n.lower() for n in group["names"]}
        matching = [d for d in all_dialogs if d.id == group["id"] or (d.title or "").strip().lower() in names_low]
        if not matching:
            print(f"OGOHLANTIRISH: {group['label']} topilmadi (ID: {group['id']})")
            send_tg_notification(f"OGOHLANTIRISH: {group['label']} guruhi topilmadi")
            continue
        for dialog in matching:
            batch, blk_cnt = await _scan_dialog(client, dialog, group["label"], seen_ids, existing_dm_ids, config)
            members.extend(batch)
            excluded_blocked += blk_cnt
    return members, {"existing_dm_ids": existing_dm_ids, "excluded_blocked": excluded_blocked}


async def was_juma_sent_this_month(
    client: TelegramClient, user_id: int, *, now_tashkent: datetime, history_limit: int
) -> bool:
    """Telegram DM tarixidan shu oy Juma tabrigi ketganini tekshiradi."""
    month_start = now_tashkent.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        async for msg in client.iter_messages(user_id, limit=history_limit):
            if not msg.out or not msg.date:
                continue
            if msg.date.astimezone(TASHKENT_TZ) < month_start:
                break
            if any(kw in (msg.message or "").lower() for kw in JUMA_KEYWORDS):
                return True
    except Exception as exc:
        print(f"OGOHLANTIRISH: {user_id} tarixi tekshirilmadi: {exc}")
        return True
    return False

async def _filter_eligible(
    client: TelegramClient, members: list[dict], already_sent: set[int],
    existing_dm_ids: set[int], now: datetime,
) -> tuple[list[dict], int, int]:
    history_limit = int(os.environ.get("JUMA_HISTORY_LIMIT", "100"))
    eligible, history_skipped, log_skipped = [], 0, 0
    for member in members:
        if member["id"] in already_sent:
            log_skipped += 1
            continue
        if member["id"] in existing_dm_ids and await was_juma_sent_this_month(
            client, member["id"], now_tashkent=now, history_limit=history_limit
        ):
            history_skipped += 1
            continue
        eligible.append(member)
    return eligible, history_skipped, log_skipped


async def send_to_member(
    client: TelegramClient, member: dict, text: str, config: JumaRateConfig, *, silent: bool = False
) -> None:
    """Qisqa typing koʻrsatib individual tabrikni yuboradi."""
    typing_sec = random.uniform(config.typing_min_sec, config.typing_max_sec)
    with contextlib.suppress(Exception):
        async with client.action(member["id"], "typing"):
            await asyncio.sleep(typing_sec)
    await client.send_message(member["id"], text, silent=silent)

async def _send_with_handlers(
    client: TelegramClient, member: dict, text: str, config: JumaRateConfig, label: str, *, silent: bool = False
) -> tuple[str, Optional[str]]:
    try:
        await send_to_member(client, member, text, config, silent=silent)
        return "sent", None
    except PeerFloodError:
        return "abort", f"PeerFloodError ({label})"
    except FloodWaitError as exc:
        if exc.seconds > config.max_flood_wait_sec:
            return "abort", f"FloodWait {exc.seconds}s > {config.max_flood_wait_sec}s limiti ({label})"
        print(f"FloodWait {exc.seconds + 5}s — {label}")
        await asyncio.sleep(exc.seconds + 5)
        try:
            await send_to_member(client, member, text, config, silent=silent)
            return "sent", None
        except PeerFloodError:
            return "abort", f"PeerFloodError retry paytida ({label})"
        except Exception as retry_err:
            print(f"FAIL (retry) {label}: {retry_err}")
            return "skip", None
    except (
        UserPrivacyRestrictedError, UserNotMutualContactError, InputUserDeactivatedError,
        PeerIdInvalidError, UsernameNotOccupiedError, UsernameInvalidError,
    ) as exc:
        print(f"SKIP {label}: {type(exc).__name__}")
        return "skip", None
    except Exception as exc:
        if isinstance(exc, ConnectionError) or "disconnected" in str(exc).lower():
            return "disconnect", str(exc)
        print(f"FAIL {label}: {exc}")
        return "skip", None


async def _wait_quiet_or_deadline(config: JumaRateConfig, deadline: datetime) -> bool:
    """Sokin soatlarda kutadi; deadline dan oʻtsa False qaytaradi."""
    now_loop = datetime.now(TASHKENT_TZ)
    if is_quiet_hours(now_loop, config):
        wait_q = seconds_until_quiet_ends(now_loop, config)
        if now_loop + timedelta(seconds=wait_q) >= deadline:
            return False
        send_tg_notification(
            f"🌙 Sokin soat ({config.quiet_start[0]:02d}:{config.quiet_start[1]:02d}–"
            f"{config.quiet_end[0]:02d}:{config.quiet_end[1]:02d}) — {int(wait_q // 60)} daq tanaffus."
        )
        await asyncio.sleep(wait_q)
    return datetime.now(TASHKENT_TZ) < deadline

async def _pause_between_sends(sent: int, config: JumaRateConfig, deadline: datetime) -> bool:
    delay_sec, is_batch = next_delay_seconds(sent, config)
    if datetime.now(TASHKENT_TZ) + timedelta(seconds=delay_sec) >= deadline:
        return False
    if is_batch:
        print(f"Batch tanaffus: {sent} ta yuborildi, {int(delay_sec // 60)} daq pauza...")
    await asyncio.sleep(delay_sec)
    return True

async def _run_send_loop(
    client: TelegramClient, members: list[dict], config: JumaRateConfig,
    custom_greetings: dict[str, str], already_sent: set[int], sent_log_path: Path, deadline: datetime,
) -> tuple[int, int, Optional[str], bool]:
    sent = failed = disconnects = 0
    aborted: Optional[str] = None
    hit_deadline = False
    total = len(members)
    max_raw = os.environ.get("JUMA_MAX_PER_RUN", "").strip()
    max_per_run = int(max_raw) if max_raw else None

    for i, member in enumerate(members):
        excluded, reason = is_excluded_member(member, config)
        if excluded:
            print(f"SKIP BLOK [{i+1}/{total}] id={member['id']} ({reason})")
            continue
        if not await _wait_quiet_or_deadline(config, deadline):
            hit_deadline = True
            break
        label = f"[{i+1}/{total}] id={member['id']}"
        silent = is_silent_send_time(datetime.now(TASHKENT_TZ), config)
        status, detail = await _send_with_handlers(
            client, member, pick_greeting_text(member, custom_greetings, JUMA_TEMPLATES),
            config, label, silent=silent,
        )
        if status == "sent":
            sent += 1
            disconnects = 0
            mark_sent(member["id"], already_sent, sent_log_path)
            print(f"OK {label}")
        elif status == "abort":
            aborted = f"🛑 Juma tabrigi TOʻXTATILDI: {detail}\nYuborildi: {sent}, Xato: {failed}"
            break
        elif status == "disconnect":
            disconnects += 1
            failed += 1
            with contextlib.suppress(Exception):
                await client.connect()
            if disconnects >= MAX_CONSECUTIVE_DISCONNECTS:
                aborted = f"🛑 Ulanish {disconnects} marta uzildi — TOʻXTATILDI ({sent} yuborildi)."
                break
            continue
        else:
            failed += 1
            disconnects = 0
        if (i + 1) % 25 == 0:
            send_tg_notification(f"Jarayon: {i+1}/{total}\n{sent} yuborildi, {failed} xato")
        if max_per_run and sent >= max_per_run:
            send_tg_notification(f"⏸ Bir martalik limit ({max_per_run}) ga yetdi — toʻxtatildi.")
            break
        if i + 1 < total and not await _pause_between_sends(sent, config, deadline):
            hit_deadline = True
            break
    return sent, failed, aborted, hit_deadline

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Juma tabrigi — Tez Natija guruhlari")
    parser.add_argument("--dry-run", action="store_true", help="Yubormasdan faqat hisobot chiqarish")
    parser.add_argument("--group", default=os.environ.get("JUMA_TARGET_GROUPS", "TN7"), help="Maqsad guruhlar")
    parser.add_argument("--messages-json", default=os.environ.get("JUMA_MESSAGES_JSON", ""), help="Tabriklar JSON")
    parser.add_argument("--cold-limit", type=int, default=None, help="Sovuq DM lar kunlik limiti")
    parser.add_argument("--ignore-day-check", action="store_true", help="Faqat --dry-run bilan ishlatiladi")
    return parser


async def _prepare_wave(
    client: TelegramClient, args: argparse.Namespace, config: JumaRateConfig, now: datetime, sent_log_path: Path
) -> tuple[list[dict], list[dict], set[int], str]:
    target_groups = select_target_groups(args.group)
    if not target_groups:
        raise ValueError(f"Guruh topilmadi: {args.group}")
    members, stats = await collect_members(client, target_groups, config)
    already_sent = load_already_sent(sent_log_path)
    eligible, hist_skip, log_skip = await _filter_eligible(client, members, already_sent, stats["existing_dm_ids"], now)
    wave, deferred = classify_and_order_recipients(eligible, cold_limit=config.cold_daily_limit)
    warm_cnt = sum(1 for m in wave if m.get("warm") or m.get("mutual"))
    est_min = estimate_duration_minutes(len(wave), config)
    est_end = now + timedelta(minutes=est_min)
    summary = (
        f"Juma reja ({args.group}): jami={len(members)}, bloklangan={stats['excluded_blocked']}, "
        f"tarix-skip={hist_skip}, log-skip={log_skip}\n"
        f"Toʻlqin={len(wave)} (issiq={warm_cnt}, sovuq={len(wave) - warm_cnt}), "
        f"keyingiga={len(deferred)}, ~{int(est_min)} daq (tugash ~{est_end.strftime('%H:%M')})"
    )
    return wave, deferred, already_sent, summary

async def run(args: argparse.Namespace) -> None:
    """Asosiy Juma tabrigi oqimi."""
    if args.ignore_day_check and not args.dry_run:
        raise ValueError("--ignore-day-check faqat --dry-run bilan ishlatiladi")
    config = load_juma_rate_config()
    if args.cold_limit is not None:
        config = replace(config, cold_daily_limit=max(0, args.cold_limit))
    now = datetime.now(TASHKENT_TZ)
    if not args.ignore_day_check and not is_juma_send_window(now, config):
        print(f"Hozir ({now.strftime('%Y-%m-%d %A %H:%M')}) Juma yuborish oynasida emas.")
        return
    deadline = compute_juma_deadline(now, config)
    sent_log_path = SENT_LOG_DIR / f"{deadline.strftime('%Y-%m-%d')}.json"
    custom = load_custom_greetings(Path(args.messages_json) if args.messages_json else None)
    source = prepare(DEDICATED_SESSION_ENV, require_dedicated=True)
    client = TelegramClient(StringSession(source.string), int(os.environ["API_ID"]), os.environ["API_HASH"])
    try:
        await guarded_connect(client, source)
        if not await guarded_is_authorized(client, source):
            send_tg_notification(f"❌ Session yaroqsiz ({source.origin}).")
            return
        wave, deferred, already_sent, summary = await _prepare_wave(client, args, config, now, sent_log_path)
        print(summary)
        if args.dry_run:
            send_tg_notification(f"🧪 DRY-RUN\n{summary}")
            return
        if not wave:
            send_tg_notification("Juma tabrigi: bu toʻlqinda yuboriladigan yangi aʼzo qolmadi.")
            return
        send_tg_notification(f"▶️ {summary}")
        sent, failed, aborted, hit_deadline = await _run_send_loop(
            client, wave, config, custom, already_sent, sent_log_path, deadline
        )
        if hit_deadline:
            send_tg_notification(f"⏰ Juma Shomi ({deadline.strftime('%H:%M')}) yetdi: {sent}/{len(wave)}")
        if aborted:
            send_tg_notification(aborted)
        done = f"Juma tabrigi yakunlandi: {sent} yuborildi, {failed} xato, {len(deferred)} keyingi haftaga."
        send_tg_notification(done)
        print(done)
    finally:
        await client.disconnect()


async def main(argv: Optional[list[str]] = None) -> None:
    """Single-flight himoyasi bilan ishga tushiradi."""
    args = _build_parser().parse_args(argv)
    try:
        with single_flight("userbot_oneoff"):
            await run(args)
    except (SessionConflictError, SessionMissingError) as exc:
        print(f"TOʻXTATILDI: {exc}")
        send_tg_notification(f"⛔️ Juma tabrigi toʻxtatildi\n\n{exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
