"""One-time Telegram login for a sales manager's card-watch session.

Run ON THE SERVER (Hetzner), interactively, with the manager present to read the
login code from their Telegram app:

    python scripts/card_watch_login.py --manager shahnoza

The manager types the code (and 2FA password, if set) themselves. The resulting
StringSession is written ONLY to the secrets env file (default
``/etc/oisha/card_watch.env``, mode 0600) as ``CARD_WATCH_SESSION_<KEY>=...``.
It is never printed and never written inside the repository.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = "/etc/oisha/card_watch.env"


def _upsert_env(path: Path, key: str, value: str) -> None:
    if REPO_ROOT in path.resolve().parents:
        sys.exit("Refusing to write a session inside the repository.")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.exists():
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


async def _login(api_id: int, api_hash: str, phone: str) -> tuple[str, str]:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        await client.send_code_request(phone)
        code = input("Telegramʼga kelgan kodni kiriting: ").strip()
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            await client.sign_in(password=getpass.getpass("2FA parol: "))
        me = await client.get_me()
        return client.session.save(), f"@{me.username or me.id}"
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager", required=True, help="manager key, e.g. shahnoza")
    parser.add_argument("--env-file", default=os.getenv("CARD_WATCH_ENV_FILE", DEFAULT_ENV_FILE))
    args = parser.parse_args()

    api_id = int(os.getenv("API_ID", "0") or 0)
    api_hash = os.getenv("API_HASH", "")
    if not api_id or not api_hash:
        sys.exit("API_ID / API_HASH must be exported in the environment.")
    key = f"CARD_WATCH_SESSION_{args.manager.strip().upper()}"
    phone = input("Menejer telefon raqami (+998...): ").strip()
    session_str, who = asyncio.run(_login(api_id, api_hash, phone))
    prod = {os.getenv("USERBOT_SESSION_STRING", ""), os.getenv("TELEGRAM_MCP_SESSION_STRING", "")}
    if session_str in prod:
        sys.exit("Session equals a prod session; aborting.")
    _upsert_env(Path(args.env_file), key, session_str)
    print(f"OK: {who} -> {key} saqlandi ({args.env_file}, 0600). Endi: systemctl restart oisha")


if __name__ == "__main__":
    main()
