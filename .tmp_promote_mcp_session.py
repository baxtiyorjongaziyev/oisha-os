from __future__ import annotations

import asyncio
import hmac
import os
import stat
from pathlib import Path

from dotenv import dotenv_values
from telethon import TelegramClient
from telethon.sessions import SQLiteSession, StringSession


ROOT = Path("/home/ubuntu/oisha-os")
ENV_PATH = ROOT / ".env"
SOURCE_PATH = ROOT / "data/userbot_session.session"
DEDICATED_PATH = ROOT / "data/telegram_mcp_dedicated.session"


def update_environment(session_string: str) -> None:
    updates = {
        "TELEGRAM_MCP_ENABLED": "true",
        "TELEGRAM_MCP_SESSION_STRING": session_string,
        "TELEGRAM_MCP_UPSTREAM_URL": "http://127.0.0.1:8765/mcp",
        "TELEGRAM_MCP_APPROVAL_TTL_SECONDS": "900",
    }
    keys = set(updates)
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line.partition("=")[0].strip() not in keys]
    kept.extend(f"{key}={value}" for key, value in updates.items())
    temp = ENV_PATH.with_name(".env.tmp-telegram-mcp")
    temp.write_text("\n".join(kept) + "\n", encoding="utf-8")
    os.chmod(temp, stat.S_IMODE(ENV_PATH.stat().st_mode))
    os.replace(temp, ENV_PATH)


async def main() -> None:
    values = dotenv_values(ENV_PATH)
    api_id = int((values.get("API_ID") or "0").strip())
    api_hash = (values.get("API_HASH") or "").strip()
    owner_id = int((values.get("OWNER_ID") or "0").strip())
    production = (values.get("USERBOT_SESSION_STRING") or "").strip()
    if not SOURCE_PATH.exists() or not api_id or not api_hash or not owner_id:
        raise SystemExit("MCP session yoki Telegram konfiguratsiyasi topilmadi")

    production_key = StringSession(production).auth_key.key if production else b""
    source = SQLiteSession(str(SOURCE_PATH))
    if not source.auth_key or not source.auth_key.key:
        source.close()
        raise SystemExit("Yangi MCP session auth key topilmadi")
    if production_key and hmac.compare_digest(source.auth_key.key, production_key):
        source.close()
        raise SystemExit("Yangi MCP session production session bilan bir xil")

    portable = StringSession()
    portable.set_dc(source.dc_id, source.server_address, source.port)
    portable.auth_key = source.auth_key
    dedicated_string = portable.save()

    client = TelegramClient(source, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise SystemExit("Yangi MCP session authorized emas")
        me = await client.get_me()
        if not me or int(me.id) != owner_id:
            raise SystemExit("Yangi MCP session ownerga mos emas")
    finally:
        await client.disconnect()

    update_environment(dedicated_string)
    os.replace(SOURCE_PATH, DEDICATED_PATH)
    os.chmod(DEDICATED_PATH, 0o600)
    print("mcp_session_promoted=true distinct_from_production=true owner_match=true")


asyncio.run(main())
