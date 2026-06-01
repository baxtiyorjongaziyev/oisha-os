from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession


DATA_DIR = Path("data")
CODE_FILE = DATA_DIR / "userbot_auth_code.txt"
PASSWORD_FILE = DATA_DIR / "userbot_auth_password.txt"
SESSION_FILE = DATA_DIR / "userbot_session_string.txt"
STATUS_FILE = DATA_DIR / "userbot_auth_status.json"
WAIT_SECONDS = int(os.getenv("USERBOT_AUTH_WAIT_SECONDS", "600"))


def write_status(state: str, **details: object) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"state": state, "updated_at": int(time.time()), **details}
    STATUS_FILE.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(STATUS_FILE, 0o600)


async def wait_for_secret(path: Path, state: str) -> str:
    write_status(state)
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            path.unlink(missing_ok=True)
            if value:
                return value
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Timed out while waiting for {path.name}")


def update_dotenv_session(session_string: str) -> None:
    env_path = Path(".env")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    replacement = f"USERBOT_SESSION_STRING={session_string}"
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("USERBOT_SESSION_STRING="):
            updated.append(replacement)
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(replacement)
    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


async def main() -> int:
    load_dotenv(".env")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CODE_FILE.unlink(missing_ok=True)
    PASSWORD_FILE.unlink(missing_ok=True)

    phone = os.getenv("TELEGRAM_PHONE", "").strip()
    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    if not phone or not api_id or not api_hash:
        write_status("failed", reason="TELEGRAM_PHONE, API_ID, or API_HASH missing")
        return 1

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        code = await wait_for_secret(CODE_FILE, "waiting_code")
        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=sent_code.phone_code_hash,
            )
        except SessionPasswordNeededError:
            password = os.getenv("TELEGRAM_PASSWORD", "").strip()
            if not password:
                password = await wait_for_secret(PASSWORD_FILE, "waiting_password")
            await client.sign_in(password=password)

        if not await client.is_user_authorized():
            write_status("failed", reason="Telegram session is not authorized")
            return 1

        session_string = client.session.save()
        SESSION_FILE.write_text(session_string, encoding="utf-8")
        os.chmod(SESSION_FILE, 0o600)
        update_dotenv_session(session_string)
        me = await client.get_me()
        write_status(
            "authorized",
            user_id=getattr(me, "id", None),
            username=getattr(me, "username", None),
        )
        return 0
    except Exception as exc:
        write_status("failed", reason=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        await client.disconnect()
        CODE_FILE.unlink(missing_ok=True)
        PASSWORD_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
