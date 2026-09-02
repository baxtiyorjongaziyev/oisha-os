"""Automated Meta Instagram Graph API Setup and Verification Tool.

Connects Facebook Page to Instagram Business/Creator Account, fetches the
Instagram User ID, tests Graph API endpoints, and updates the environment.
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.services.core.instagram_weekly_report import InstagramWeeklyReportAgent

logger = logging.getLogger(__name__)
DEFAULT_PAGE_ID = "103894334533931"
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def update_env_file(env_path: Path, updates: Dict[str, str]) -> None:
    """Safely updates or appends key-value pairs in the .env file."""
    lines: list[str] = []
    existing_keys: set[str] = set()

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}")
                    existing_keys.add(key)
                    continue
            lines.append(line)

    for key, value in updates.items():
        if key not in existing_keys:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[META-SETUP] Updated .env with %d keys", len(updates))


async def fetch_meta_details(page_id: str, access_token: str) -> Dict[str, Any]:
    """Fetches Facebook Page details and linked Instagram account ID."""
    url = f"{GRAPH_BASE}/{page_id}"
    params = {
        "fields": "id,name,instagram_business_account,access_token",
        "access_token": access_token,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": response.text,
            }
        return {"ok": True, "data": response.json()}


async def run_setup(token: str, page_id: str = DEFAULT_PAGE_ID, write_env: bool = True) -> int:
    """Executes the setup and verification pipeline."""
    token = token.strip()
    if not token:
        print("[ERROR] Meta Access Token is empty.")
        return 1

    print(f"[*] Verifying Facebook Page '{page_id}' with Meta Graph API...")
    details = await fetch_meta_details(page_id, token)
    if not details.get("ok"):
        print(f"[ERROR] Failed to query Meta Graph API ({details.get('status_code')}):")
        print(details.get("error"))
        return 1

    data = details.get("data", {})
    page_name = data.get("name", "Unknown Page")
    ig_account = data.get("instagram_business_account")
    ig_user_id = ig_account.get("id") if isinstance(ig_account, dict) else None

    print(f"[OK] Facebook Page found: '{page_name}' (ID: {page_id})")
    if not ig_user_id:
        print(f"[WARNING] No linked 'instagram_business_account' found on Page '{page_name}'.")
        print("Please ensure your Instagram Professional account is connected to this Facebook Page in Meta Business Suite.")
        return 2

    print(f"[OK] Instagram Business Account ID: {ig_user_id}")

    if write_env:
        env_file = ROOT / ".env"
        updates = {
            "META_PAGE_ACCESS_TOKEN": token,
            "META_PAGE_ID": page_id,
            "META_INSTAGRAM_USER_ID": ig_user_id,
            "META_GRAPH_API_VERSION": GRAPH_API_VERSION,
        }
        update_env_file(env_file, updates)
        print(f"[OK] Updated local .env at: {env_file}")

    # Test report generation
    print("\n[*] Testing Instagram Weekly Report generation...")
    os.environ["META_PAGE_ACCESS_TOKEN"] = token
    os.environ["META_INSTAGRAM_USER_ID"] = ig_user_id
    os.environ["META_PAGE_ID"] = page_id

    agent = InstagramWeeklyReportAgent()
    result = await agent.run()
    report = result.get("report", "")
    posts_count = len(result.get("posts", []))

    print(f"[OK] Successfully fetched {posts_count} weekly post(s).")
    print("\n--- REPORT PREVIEW ---")
    print(html.unescape(report))
    print("----------------------")
    return 0


def main() -> int:
    import asyncio

    parser = argparse.ArgumentParser(description="Automated Meta Instagram Setup")
    parser.add_argument("--token", type=str, help="Meta Page Access Token")
    parser.add_argument("--page-id", type=str, default=DEFAULT_PAGE_ID, help="Facebook Page ID")
    parser.add_argument("--no-env", action="store_true", help="Do not write to .env file")
    args = parser.parse_args()

    token = args.token or os.environ.get("META_PAGE_ACCESS_TOKEN", "")
    if not token:
        print("[!] No token provided. Pass --token <access_token> or set META_PAGE_ACCESS_TOKEN.")
        return 1

    return asyncio.run(run_setup(token=token, page_id=args.page_id, write_env=not args.no_env))


if __name__ == "__main__":
    raise SystemExit(main())
