import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
)
from telethon.sessions import StringSession

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
STATE_FILE = DATA_DIR / "telegram_auth_state.json"
CODE_FILE = DATA_DIR / "telegram_code.txt"
PWD_FILE = DATA_DIR / "telegram_password.txt"
ENV_FILE = ROOT_DIR / ".env"

def update_env_file(key: str, value: str):
    if not ENV_FILE.exists():
        return
    content = ENV_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}=") or line.startswith(f'export {key}='):
            new_lines.append(f'{key}="{value}"')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'{key}="{value}"')
    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

def update_github_secret(key: str, value: str):
    try:
        proc = subprocess.run(
            ["gh", "secret", "set", key, "-b", value],
            capture_output=True,
            text=True,
            timeout=15
        )
        if proc.returncode == 0:
            print(f"[AUTH] Successfully updated GitHub Secret {key}!", flush=True)
        else:
            print(f"[AUTH] Warning: Failed to set GitHub secret {key}: {proc.stderr}", flush=True)
    except Exception as e:
        print(f"[AUTH] Warning: Could not update GitHub secret: {e}", flush=True)

def write_state(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

async def complete_login(code: str, password: str = None):
    load_dotenv(ENV_FILE)
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")

    if not STATE_FILE.exists():
        print("[ERROR] No pending auth state found.", flush=True)
        sys.exit(1)

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    pending_session = state.get("pending_session")
    phone = state.get("phone")
    phone_code_hash = state.get("phone_code_hash")

    if not (pending_session and phone and phone_code_hash):
        print("[ERROR] Incomplete pending state.", flush=True)
        sys.exit(1)

    client = TelegramClient(StringSession(pending_session), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if not password:
            print("[AUTH] 2FA Password required!", flush=True)
            write_state({**state, "status": "waiting_for_password"})
            await client.disconnect()
            sys.exit(2)
        await client.sign_in(password=password)
    except PhoneCodeExpiredError:
        print("[AUTH] Kod muddati tugagan! Yangi kod so'ralmoqda...", flush=True)
        sent = await client.send_code_request(phone)
        write_state({
            "status": "waiting_for_code",
            "phone": phone,
            "phone_code_hash": sent.phone_code_hash,
            "pending_session": client.session.save(),
            "timestamp": time.time(),
            "expired_previous": True
        })
        await client.disconnect()
        sys.exit(3)
    except PhoneCodeInvalidError:
        print("[AUTH] Xato kod kiritildi! Iltimos, qaytadan tekshirib kiriting.", flush=True)
        await client.disconnect()
        sys.exit(4)

    session_str = client.session.save()
    me = await client.get_me()
    username = getattr(me, "username", "") or getattr(me, "first_name", "")
    print(f"[AUTH] Successfully authorized as {username}!", flush=True)

    (DATA_DIR / "userbot_session_string.txt").write_text(session_str, encoding="utf-8")
    update_env_file("USERBOT_SESSION_STRING", session_str)
    update_github_secret("USERBOT_SESSION_STRING", session_str)

    write_state({
        "status": "success",
        "username": username,
        "phone": phone,
        "session_string": session_str
    })
    await client.disconnect()

async def run_auth():
    load_dotenv(ENV_FILE)
    api_id_str = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("TG_PHONE")

    if not (api_id_str and api_hash and phone):
        write_state({"status": "error", "message": "Missing API_ID, API_HASH, or TG_PHONE in .env"})
        print("[ERROR] Missing credentials in .env", flush=True)
        sys.exit(1)

    api_id = int(api_id_str)
    phone = phone.strip().strip("'\"").replace(" ", "").replace("-", "")
    print(f"[AUTH] Connecting to Telegram for {phone}...", flush=True)

    if CODE_FILE.exists():
        CODE_FILE.unlink()
    if PWD_FILE.exists():
        PWD_FILE.unlink()

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"[AUTH] Requesting code for {phone}...", flush=True)
        sent = await client.send_code_request(phone)
        phone_code_hash = sent.phone_code_hash
        pending_session = client.session.save()
        print(f"[AUTH] Code requested! phone_code_hash={phone_code_hash}", flush=True)
        write_state({
            "status": "waiting_for_code",
            "phone": phone,
            "phone_code_hash": phone_code_hash,
            "pending_session": pending_session,
            "timestamp": time.time()
        })

        code = None
        for _ in range(600):
            if CODE_FILE.exists():
                text = CODE_FILE.read_text(encoding="utf-8").strip()
                if text:
                    code = text
                    break
            await asyncio.sleep(1)

        if not code:
            write_state({"status": "error", "message": "Timeout waiting for code"})
            print("[ERROR] Timeout waiting for verification code", flush=True)
            await client.disconnect()
            sys.exit(1)

        print(f"[AUTH] Code received: {code}. Signing in...", flush=True)
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            print("[AUTH] 2FA Password required!", flush=True)
            write_state({
                "status": "waiting_for_password",
                "phone": phone,
                "pending_session": client.session.save(),
                "phone_code_hash": phone_code_hash
            })
            password = None
            for _ in range(600):
                if PWD_FILE.exists():
                    text = PWD_FILE.read_text(encoding="utf-8").strip()
                    if text:
                        password = text
                        break
                await asyncio.sleep(1)

            if not password:
                write_state({"status": "error", "message": "Timeout waiting for 2FA password"})
                print("[ERROR] Timeout waiting for 2FA password", flush=True)
                await client.disconnect()
                sys.exit(1)

            await client.sign_in(password=password)

    session_str = client.session.save()
    me = await client.get_me()
    username = getattr(me, "username", "") or getattr(me, "first_name", "")
    print(f"[AUTH] Successfully authorized as {username}!", flush=True)

    (DATA_DIR / "userbot_session_string.txt").write_text(session_str, encoding="utf-8")
    update_env_file("USERBOT_SESSION_STRING", session_str)
    update_github_secret("USERBOT_SESSION_STRING", session_str)

    write_state({
        "status": "success",
        "username": username,
        "phone": phone,
        "session_string": session_str
    })
    await client.disconnect()
    print("[AUTH] Completed successfully.", flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--complete":
        code_arg = sys.argv[2]
        pwd_arg = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(complete_login(code_arg, pwd_arg))
    else:
        asyncio.run(run_auth())
