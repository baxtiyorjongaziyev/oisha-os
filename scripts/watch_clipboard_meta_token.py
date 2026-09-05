"""Clipboard watcher for Meta Access Token.

Continuously monitors the Windows clipboard for Meta Graph API tokens (EAA...),
automatically applies them to .env via setup_meta_instagram.py, and verifies the setup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


def get_clipboard_text() -> str:
    """Reads current clipboard text via PowerShell."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.stdout.strip()
    except Exception:
        return ""


async def main() -> int:
    print("[*] Clipboard watcher started. Monitoring for Meta Access Token (EAA...)...")
    result_file = ROOT / "tmp" / "meta_setup_result.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    timeout_seconds = 600  # 10 minutes

    while time.time() - start_time < timeout_seconds:
        text = get_clipboard_text()
        if text.startswith("EAA") and len(text) > 40:
            print("[+] Meta Access Token detected in clipboard!")
            from scripts.setup_meta_instagram import run_setup

            exit_code = await run_setup(token=text)
            status_data = {
                "ok": exit_code == 0,
                "exit_code": exit_code,
                "timestamp": time.time(),
            }
            result_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
            print(f"[*] Setup finished with code {exit_code}. Results saved to {result_file}")
            return exit_code

        await asyncio.sleep(2)

    print("[-] Watcher timed out waiting for token in clipboard.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
