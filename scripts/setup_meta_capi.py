#!/usr/bin/env python3
"""Meta Conversions API (Conversion Leads) setup and verification tool.

Verifies Dataset ID and Access Token with Meta Graph API, tests event dispatch,
and updates .env.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MetaCAPISetup")


def get_clipboard_text() -> str:
    """Reads current clipboard text via PowerShell safely without encoding errors."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Clipboard"],
            capture_output=True,
            timeout=5,
        )
        return res.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def test_meta_capi_event(
    dataset_id: str, access_token: str, test_code: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a test event to Meta Graph API to verify credentials."""
    url = f"https://graph.facebook.com/v21.0/{dataset_id}/events"
    payload = {
        "data": [
            {
                "event_name": "Lead",
                "event_time": int(time.time()),
                "action_source": "system_generated",
                "user_data": {
                    "lead_id": "test_verification_001",
                },
                "custom_data": {
                    "event_source": "crm",
                    "lead_event_source": "Oisha-OS Verification",
                },
            }
        ],
        "access_token": access_token,
    }
    if test_code:
        payload["test_event_code"] = test_code

    try:
        res = requests.post(url, json=payload, timeout=15)
        return {
            "status_code": res.status_code,
            "data": res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text,
            "ok": res.status_code == 200,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def update_env_file(env_path: Path, updates: Dict[str, str]) -> None:
    """Updates key-value pairs in the target .env file."""
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
    logger.info("Updated %s with %d keys", env_path, len(updates))


async def run_setup(
    dataset_id: Optional[str] = None,
    access_token: Optional[str] = None,
    test_code: Optional[str] = None,
    watch_clipboard: bool = False,
) -> int:
    env_file = ROOT / ".env"

    if watch_clipboard and (not dataset_id or not access_token):
        print("\n[*] Clipboard monitoring active (10 minutes)...")
        print("    1. Nusxa oling: Meta Events Manager -> Settings -> Dataset ID")
        print("    2. Nusxa oling: Meta Events Manager -> Settings -> Generate Access Token")
        start = time.time()
        last_clip = ""
        while time.time() - start < 600:
            clip = get_clipboard_text()
            if clip and clip != last_clip:
                last_clip = clip
                if clip.isdigit() and 10 <= len(clip) <= 20 and not dataset_id:
                    dataset_id = clip
                    print(f"  [+] Dataset ID aniqlandi: {dataset_id}")
                elif clip.startswith("EAA") and len(clip) > 50 and not access_token:
                    access_token = clip
                    print(f"  [+] Access Token aniqlandi: {access_token[:15]}... ({len(access_token)} chars)")
                elif clip.startswith("TEST") and not test_code:
                    test_code = clip
                    print(f"  [+] Test Event Code aniqlandi: {test_code}")

            if dataset_id and access_token:
                break
            await asyncio.sleep(1.5)

    if not dataset_id or not access_token:
        print("\n[!] Dataset ID yoki Access Token yetarli emas.")
        print(f"    Dataset ID: {dataset_id or 'Kutilmoqda...'}")
        print(f"    Access Token: {'Mavjud' if access_token else 'Kutilmoqda...'}")
        return 1

    print("\n[*] Meta Graph API bilan tekshirilmoqda...")
    res = test_meta_capi_event(dataset_id, access_token, test_code)
    print(f"    Javob kodi: {res.get('status_code')}")
    print(f"    Javob ma'lumoti: {json.dumps(res.get('data'), indent=2)}")

    if not res.get("ok"):
        print("\n[X] Meta token yoki Dataset ID rad etildi. Iltimos tekshirib qayta urinib ko'ring.")
        return 2

    print("\n[V] Muvaffaqiyatli! Meta test hodisasini qabul qildi.")
    updates = {
        "META_CAPI_ENABLED": "True",
        "META_CAPI_DATASET_ID": dataset_id,
        "META_CAPI_ACCESS_TOKEN": access_token,
    }
    if test_code:
        updates["META_CAPI_TEST_EVENT_CODE"] = test_code

    update_env_file(env_file, updates)
    print(f"[V] Mahalliy {env_file} yangilandi.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Setup Meta CAPI Credentials")
    parser.add_argument("--dataset-id", help="Meta Dataset / Pixel ID (digits)")
    parser.add_argument("--token", help="Meta Conversions API Access Token (EAA...)")
    parser.add_argument("--test-code", help="Test Event Code from Test Events tab (optional)")
    parser.add_argument("--watch", action="store_true", help="Watch clipboard for copied values")
    args = parser.parse_args()

    exit_code = asyncio.run(
        run_setup(
            dataset_id=args.dataset_id,
            access_token=args.token,
            test_code=args.test_code,
            watch_clipboard=args.watch or (not args.dataset_id or not args.token),
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
