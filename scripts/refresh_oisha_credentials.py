#!/usr/bin/env python3
"""Utility to refresh Oisha‑OS credentials.

This script performs two independent actions:
1. **Telethon user‑bot session** – generates a fresh ``USERBOT_SESSION_STRING``.
2. **AmoCRM OAuth** – obtains a new ``AMOCRM_REFRESH_TOKEN``.

Both values are written back to the project's ``.env`` file and the
``oisha‑os`` systemd service is restarted.

The script is **interactive** – it requires you to paste the verification
code for Telegram and the ``code`` query‑parameter from the AmoCRM OAuth
redirect.  It is safe to run on the Oracle VM where the service lives.
"""

import os
import sys
import pathlib
import configparser
from urllib.parse import urlencode

# ==== Telethon (user‑bot) ====
from telethon import TelegramClient
from telethon.sessions import StringSession

# ==== HTTP for AmoCRM ====
import requests

ENV_PATH = pathlib.Path(__file__).resolve().parents[1] / ".env"

def load_env(path: pathlib.Path) -> dict:
    """Load key/value pairs from a ``.env`` file.

    The file is simple ``KEY=VALUE`` lines; comments are ignored.
    """
    data: dict = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            # Strip surrounding quotes if present
            v = v.strip('"')
            data[k] = v
    return data

def save_env(path: pathlib.Path, data: dict) -> None:
    """Write the dictionary back to ``.env`` preserving order where possible.
    Existing keys are overwritten; unknown keys are appended.
    """
    lines = []
    existing_keys = set()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    lines.append(line)
                    continue
                k, _ = stripped.split("=", 1)
                existing_keys.add(k)
                if k in data:
                    lines.append(f"{k}=\"{data[k]}\"\n")
                    del data[k]
                else:
                    lines.append(line)
    # Append any new keys
    for k, v in data.items():
        lines.append(f"{k}=\"{v}\"\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def refresh_userbot(env: dict) -> str:
    api_id = int(env.get("API_ID", "0"))
    api_hash = env.get("API_HASH")
    phone = env.get("TG_PHONE")
    if not (api_id and api_hash and phone):
        print("[ERROR] Missing TELEGRAM API credentials in .env", file=sys.stderr)
        sys.exit(1)
    print("=== Refreshing Telethon user-bot session ===")
    client = TelegramClient(StringSession(), api_id, api_hash)
    # ``client.start`` handles the whole flow: it will ask for the code.
    client.start(phone=phone)
    session_str = client.session.save()
    print("[OK] New session string generated.")
    return session_str

def refresh_amocrm(env: dict) -> str:
    subdomain = env.get("AMOCRM_SUBDOMAIN")
    client_id = env.get("AMOCRM_CLIENT_ID")
    client_secret = env.get("AMOCRM_CLIENT_SECRET")
    redirect_uri = env.get("AMOCRM_REDIRECT_URL")
    if not (subdomain and client_id and client_secret and redirect_uri):
        print("[ERROR] Missing AmoCRM config in .env", file=sys.stderr)
        sys.exit(1)
    auth_url = (
        f"https://{subdomain}.amocrm.com/oauth?" +
        urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": "cli",
        })
    )
    print("=== Refreshing AmoCRM OAuth ===")
    print("Open the following URL in a browser, log in, and copy the "
          "'code' query parameter from the redirected URL:")
    print(auth_url)
    code = input("Enter the 'code' value: ").strip()
    token_endpoint = f"https://{subdomain}.amocrm.com/oauth2/access_token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(token_endpoint, data=payload, timeout=15)
    if resp.status_code != 200:
        print(f"[ERROR] AmoCRM token request failed: {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print("[ERROR] No refresh_token in response.", file=sys.stderr)
        sys.exit(1)
    print("[OK] New AmoCRM refresh token obtained.")
    return refresh_token

def restart_service():
    print("=== Restarting oisha‑os systemd service ===")
    import subprocess
    subprocess.run(["systemctl", "restart", "oisha‑os.service"], check=False)
    print("Service restart command issued. Use 'systemctl status oisha‑os.service' to verify.")

def main():
    if not ENV_PATH.exists():
        print(f"[ERROR] .env not found at {ENV_PATH}", file=sys.stderr)
        sys.exit(1)
    env = load_env(ENV_PATH)
    # 1. Refresh user‑bot
    new_session = refresh_userbot(env)
    env["USERBOT_SESSION_STRING"] = new_session
    # 2. Refresh AmoCRM token
    new_refresh = refresh_amocrm(env)
    env["AMOCRM_REFRESH_TOKEN"] = new_refresh
    # 3. Persist changes
    save_env(ENV_PATH, env)
    print(f"[INFO] Updated .env at {ENV_PATH}")
    # 4. Restart service
    restart_service()

if __name__ == "__main__":
    main()
