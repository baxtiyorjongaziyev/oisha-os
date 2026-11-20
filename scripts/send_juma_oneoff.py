"""Bir martalik Juma tabrigi — kun tekshiruvsiz, TN7 (yoki tanlangan guruh) ga."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import random
import sys
import urllib.parse
import urllib.request
from dataclasses import replace
from datetime import datetime
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
    estimate_duration_minutes, is_excluded_juma_recipient, is_excluded_member,
    is_silent_send_time, load_custom_greetings, load_juma_rate_config, match_group_dialogs,
    next_delay_seconds, pick_greeting_text, select_target_groups,
)

MAX_CONSECUTIVE_DISCONNECTS = 3
DEDICATED_SESSION_ENV = "JUMA_SESSION_STRING"


def notify(text: str) -> None:
    """Owner Telegramiga qisqa bildirishnoma yuboradi."""
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


def _assert_test_user_allowed(username: str, config: JumaRateConfig) -> None:
    excluded, reason = is_excluded_juma_recipient(
        username,
        blocked_username_tokens=config.blocked_username_tokens,
        blocked_brand_tokens=config.blocked_brand_tokens,
        blocked_exact_usernames=config.blocked_exact_usernames,
        blocked_user_ids=config.blocked_user_ids,
    )
    if excluded:
        raise ValueError(f"@{username.lstrip('@')} rad etildi ({reason}) — bloklangan roʻyxatda.")


async def send_test(
    client: TelegramClient, username: str, config: JumaRateConfig, custom: dict[str, str]
) -> None:
    """Bitta foydalanuvchiga test xabar yuboradi (bloklangan roʻyxat tekshiriladi)."""
    _assert_test_user_allowed(username, config)
    text = pick_greeting_text({"id": username, "username": username}, custom, JUMA_TEMPLATES)
    print(f"Test xabar yuborilmoqda: @{username.lstrip('@')}\nMatn:\n{text}\n")
    await client.send_message(username, text)
    print(f"OK — @{username.lstrip('@')} ga yuborildi!")
    notify(f"Test Juma tabrigi @{username.lstrip('@')} ga yuborildi!")


async def _scan_oneoff_dialog(
    client: TelegramClient, dialog, seen_ids: set[int], existing_dm_ids: set[int], config: JumaRateConfig
) -> tuple[list[dict], int]:
    rows, excluded_blocked = [], 0
    title = (dialog.title or "").strip()
    print(f"Guruh topildi: {title} (ID: {dialog.id})")
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
            rows.append({
                "id": user.id, "username": uname, "name": full_name,
                "mutual": mutual, "warm": mutual or (user.id in existing_dm_ids),
            })
    except ChatAdminRequiredError:
        print(f"  SKIP {title}: admin huquqi kerak")
    except Exception as exc:
        print(f"  SKIP {title}: {exc}")
    return rows, excluded_blocked


async def collect_group_members(
    client: TelegramClient, target_groups: list[dict], config: JumaRateConfig
) -> tuple[list[dict], int]:
    """Tanlangan guruhlardan aʼzolarni yigʻadi va bloklangan aʼzolarni chiqarib tashlaydi."""
    dialog_limit = max(50, int(os.environ.get("JUMA_DIALOG_SCAN_LIMIT", "400")))
    all_dialogs = [d async for d in client.iter_dialogs(limit=dialog_limit)]
    existing_dm_ids = {d.entity.id for d in all_dialogs if d.is_user and getattr(d, "entity", None)}
    seen_ids: set[int] = set()
    members: list[dict] = []
    excluded_blocked = 0
    for group in target_groups:
        matching = match_group_dialogs(all_dialogs, group)
        if not matching:
            print(f"XATO: {group['label']} guruhi topilmadi (ID: {group['id']})")
            notify(f"XATO: {group['label']} guruhi topilmadi")
            continue
        for dialog in matching:
            batch, blk_cnt = await _scan_oneoff_dialog(client, dialog, seen_ids, existing_dm_ids, config)
            members.extend(batch)
            excluded_blocked += blk_cnt
    return members, excluded_blocked


async def _send_one(
    client: TelegramClient, member: dict, text: str, config: JumaRateConfig, label: str
) -> tuple[str, Optional[str]]:
    silent = is_silent_send_time(datetime.now(TASHKENT_TZ), config)
    try:
        typing_sec = random.uniform(config.typing_min_sec, config.typing_max_sec)
        with contextlib.suppress(Exception):
            async with client.action(member["id"], "typing"):
                await asyncio.sleep(typing_sec)
        await client.send_message(member["id"], text, silent=silent)
        return "sent", None
    except PeerFloodError:
        return "abort", f"PeerFloodError ({label})"
    except FloodWaitError as exc:
        if exc.seconds > config.max_flood_wait_sec:
            return "abort", f"FloodWait {exc.seconds}s > {config.max_flood_wait_sec}s limiti"
        print(f"FloodWait {exc.seconds + 5}s — {label}")
        await asyncio.sleep(exc.seconds + 5)
        try:
            await client.send_message(member["id"], text, silent=silent)
            return "sent", None
        except PeerFloodError:
            return "abort", f"PeerFloodError retry ({label})"
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
        if "disconnected" in str(exc).lower() or isinstance(exc, ConnectionError):
            return "disconnect", str(exc)
        print(f"FAIL {label}: {exc}")
        return "skip", None


async def _broadcast_loop(
    client: TelegramClient, wave: list[dict], config: JumaRateConfig, custom: dict[str, str]
) -> tuple[int, int]:
    sent = failed = disconnects = 0
    total = len(wave)
    for i, member in enumerate(wave):
        excluded, reason = is_excluded_member(member, config)
        if excluded:
            print(f"SKIP BLOK [{i+1}/{total}] id={member['id']} ({reason})")
            continue
        label = f"[{i+1}/{total}] id={member['id']} ({member['name']})"
        status, detail = await _send_one(
            client, member, pick_greeting_text(member, custom, JUMA_TEMPLATES), config, label
        )
        if status == "sent":
            sent += 1
            disconnects = 0
            print(f"OK {label}")
        elif status == "abort":
            notify(f"🛑 Broadcast TOʻXTATILDI: {detail}\nYuborildi: {sent}, Xato: {failed}")
            break
        elif status == "disconnect":
            disconnects += 1
            failed += 1
            with contextlib.suppress(Exception):
                await client.connect()
            if disconnects >= MAX_CONSECUTIVE_DISCONNECTS:
                notify(f"🛑 Ulanish {disconnects} marta uzildi — TOʻXTATILDI ({sent} yuborildi)")
                break
            continue
        else:
            failed += 1
            disconnects = 0
        if (i + 1) % 25 == 0:
            notify(f"Jarayon: {i+1}/{total}\n{sent} yuborildi, {failed} xato")
        if i + 1 < total:
            delay_sec, _ = next_delay_seconds(sent, config)
            await asyncio.sleep(delay_sec)
    return sent, failed


async def broadcast_group(
    client: TelegramClient, args: argparse.Namespace, config: JumaRateConfig, custom: dict[str, str]
) -> None:
    """Tanlangan guruh aʼzolariga xavfsiz pauza va limit bilan broadcast qiladi."""
    target_groups = select_target_groups(args.group)
    if not target_groups:
        raise ValueError(f"Guruh topilmadi: {args.group}")
    members, excluded_blocked = await collect_group_members(client, target_groups, config)
    wave, deferred = classify_and_order_recipients(members, cold_limit=config.cold_daily_limit)
    est_min = estimate_duration_minutes(len(wave), config)
    head = (
        f"Juma oneoff ({args.group}): jami={len(members)}, bloklangan={excluded_blocked}, "
        f"toʻlqin={len(wave)}, keyingi={len(deferred)}, ~{int(est_min)} daq"
    )
    print(head)
    if args.dry_run:
        notify(f"🧪 DRY-RUN\n{head}")
        return
    if not wave:
        notify("Juma oneoff: yuboriladigan aʼzo topilmadi.")
        return
    notify(f"▶️ {head}")
    sent, failed = await _broadcast_loop(client, wave, config, custom)
    summary = f"Juma oneoff yakunlandi: {sent} yuborildi, {failed} xato, {len(deferred)} keyingi toʻlqinga."
    notify(summary)
    print(summary)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bir martalik Juma tabrigi (TN7)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test-user", type=str, help="Test xabar yuborish uchun username")
    group.add_argument("--broadcast", action="store_true", help="Tanlangan guruhga broadcast")
    parser.add_argument("--group", default="TN7", help="Guruh kodi (masalan TN7, TN6)")
    parser.add_argument("--dry-run", action="store_true", help="Yubormasdan hisobot chiqarish")
    parser.add_argument("--messages-json", default="", help="Individual tabrik JSON fayli")
    parser.add_argument("--cold-limit", type=int, default=None, help="Sovuq DM limiti")
    return parser


async def run(args: argparse.Namespace) -> None:
    """Telethon sessiyani ulab oneoff rejimini bajaradi."""
    config = load_juma_rate_config()
    if args.cold_limit is not None:
        config = replace(config, cold_daily_limit=max(0, args.cold_limit))
    custom = load_custom_greetings(Path(args.messages_json) if args.messages_json else None)
    if args.test_user:
        _assert_test_user_allowed(args.test_user, config)
    source = prepare(DEDICATED_SESSION_ENV, require_dedicated=True)
    client = TelegramClient(StringSession(source.string), int(os.environ["API_ID"]), os.environ["API_HASH"])
    try:
        await guarded_connect(client, source)
        if not await guarded_is_authorized(client, source):
            notify(f"❌ Session muddati tugagan ({source.origin})")
            return
        if args.test_user:
            await send_test(client, args.test_user, config, custom)
        elif args.broadcast:
            await broadcast_group(client, args, config, custom)
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
        notify(f"⛔️ Juma oneoff toʻxtatildi\n\n{exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
