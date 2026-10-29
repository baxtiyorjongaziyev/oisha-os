"""CLI runner for Remote Staff Hourly Check-in.

Usage:
    python scripts/dispatch_remote_checkin.py            # Send now (respecting work hours)
    python scripts/dispatch_remote_checkin.py --force    # Force send even outside work hours
    python scripts/dispatch_remote_checkin.py --dry-run  # Print message to console without sending
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.schedulers.remote_staff_checkin_scheduler import (
    DEFAULT_REP_NAME,
    DEFAULT_REP_TG,
    build_checkin_message,
    fetch_recent_calls_for_rep,
    get_target_destination,
    is_work_hour,
    send_remote_checkin,
)
from src.time_utils import get_local_now

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dispatch_remote_checkin")


class DirectBotClient:
    """Lightweight Bot API client using requests for standalone execution."""

    def __init__(self, token: str):
        self.token = token

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "HTML",
        message_thread_id: int | None = None,
        **kwargs,
    ):
        import requests

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id

        resp = await asyncio.to_thread(requests.post, url, json=payload, timeout=20)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram Bot API error: {data}")
        return data


async def main():
    parser = argparse.ArgumentParser(description="Dispatch Remote Staff Hourly Check-in")
    parser.add_argument("--force", action="store_true", help="Force send regardless of work hours")
    parser.add_argument("--dry-run", action="store_true", help="Only render message to console")
    parser.add_argument("--rep", default=DEFAULT_REP_NAME, help="Representative name")
    parser.add_argument("--tg", default=DEFAULT_REP_TG, help="Telegram username (@handle)")
    args = parser.parse_args()

    now = get_local_now()
    chat_id, topic_id = get_target_destination()

    print(f"[*] Destination: chat={chat_id}, topic={topic_id}")
    print(f"[*] Time: {now.strftime('%Y-%m-%d %H:%M:%S')} (Work hour: {is_work_hour(now)})")

    if args.dry_run:
        end_ts = int(now.timestamp())
        start_ts = end_ts - 3600
        calls = fetch_recent_calls_for_rep(["rayxona@jonbranding.uz"], start_ts, end_ts)
        msg = build_checkin_message(args.rep, args.tg, now, calls)
        print("\n--- [DRY RUN MESSAGE PREVIEW] ---")
        print(msg)
        print("--- [END PREVIEW] ---\n")
        return

    bot_token = (
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("BOT_TOKEN", "").strip()
    )
    if not bot_token:
        from src.settings import settings
        bot_token = (
            getattr(settings, "TELEGRAM_BOT_TOKEN", None)
            or (settings.BOT_TOKEN.get_secret_value() if hasattr(settings.BOT_TOKEN, "get_secret_value") else str(settings.BOT_TOKEN))
        )

    if not bot_token:
        print("[!] ERROR: BOT_TOKEN is not configured in env or settings.")
        sys.exit(1)

    client = DirectBotClient(bot_token)
    sent = await send_remote_checkin(
        client,
        now_fn=get_local_now,
        seller_name=args.rep,
        tg_handle=args.tg,
        force=args.force,
    )
    if sent:
        print(f"[+] Check-in successfully dispatched to chat={chat_id} (topic={topic_id})")
    else:
        print("[!] Check-in not sent (check work hours or enabled flag). Use --force to override.")


if __name__ == "__main__":
    asyncio.run(main())
