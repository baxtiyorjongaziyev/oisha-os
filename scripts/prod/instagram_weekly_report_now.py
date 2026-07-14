"""Manual Instagram weekly report runner.

Safe for production diagnostics: it does not start the Telegram userbot.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.core.instagram_weekly_report import InstagramWeeklyReportAgent
from src.settings import settings


async def _send_via_bot_api(text: str) -> None:
    token = settings.BOT_TOKEN.get_secret_value() if settings.BOT_TOKEN else ""
    chat_id = settings.TEAM_GROUP_ID
    if not token or not chat_id:
        raise RuntimeError("BOT_TOKEN or TEAM_GROUP_ID missing")
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
        response.raise_for_status()


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run Instagram weekly report once")
    parser.add_argument("--status", action="store_true", help="Print Meta credential status only")
    parser.add_argument("--dry-run", action="store_true", help="Build report and print it")
    parser.add_argument("--send", action="store_true", help="Build report and send via Telegram Bot API")
    args = parser.parse_args()

    agent = InstagramWeeklyReportAgent()
    status = agent.credential_status()
    print("Instagram weekly report status:")
    for key, ok in status.items():
        print(f"- {key}: {'OK' if ok else 'MISSING'}")

    if args.status and not (args.dry_run or args.send):
        return 0 if all(status.values()) else 2

    if not (args.dry_run or args.send):
        print("\nUse --dry-run or --send.")
        return 0

    result = await agent.run()
    report = result["report"]
    print("\n--- REPORT PREVIEW ---")
    print(html.unescape(report))

    if args.send:
        await _send_via_bot_api(report)
        print("\nTelegram report sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
