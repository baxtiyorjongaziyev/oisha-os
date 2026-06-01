"""Repair Telegram bot membership in configured groups through the authorized userbot."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from dotenv import load_dotenv
from telethon import TelegramClient, functions
from telethon.errors import UserAlreadyParticipantError
from telethon.sessions import StringSession


def _bot_api(token: str, method: str, **params: Any) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = urllib.parse.urlencode(params).encode()
    request = urllib.request.Request(url, data=body)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error_code": exc.code, "description": "HTTP error"}


async def repair(*, apply: bool) -> Dict[str, Any]:
    load_dotenv(".env")
    token = os.environ["BOT_TOKEN"]
    bot = _bot_api(token, "getMe").get("result") or {}
    bot_username = bot.get("username")
    if not bot_username:
        raise RuntimeError("Bot username topilmadi")

    group_ids = sorted(
        {
            int(value)
            for value in (
                os.getenv("CRM_GROUP_ID"),
                os.getenv("TEAM_GROUP_ID"),
            )
            if value
        }
    )
    client = TelegramClient(
        StringSession(os.environ["USERBOT_SESSION_STRING"]),
        int(os.environ["API_ID"]),
        os.environ["API_HASH"],
    )
    await client.connect()
    try:
        result: Dict[str, Any] = {
            "apply": apply,
            "bot_username": bot_username,
            "groups": {},
        }
        for chat_id in group_ids:
            before = _bot_api(token, "getChat", chat_id=chat_id)
            entry: Dict[str, Any] = {
                "before_ok": bool(before.get("ok")),
                "invite_attempted": False,
                "invite_ok": False,
            }
            if apply and not before.get("ok"):
                entity = await client.get_entity(chat_id)
                entry["invite_attempted"] = True
                try:
                    await client(
                        functions.channels.InviteToChannelRequest(
                            channel=entity,
                            users=[bot_username],
                        )
                    )
                    entry["invite_ok"] = True
                except UserAlreadyParticipantError:
                    entry["invite_ok"] = True
            after = _bot_api(token, "getChat", chat_id=chat_id)
            entry["after_ok"] = bool(after.get("ok"))
            entry["after_error"] = after.get("description")
            result["groups"][str(chat_id)] = entry
        return result
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(repair(apply=args.apply)), ensure_ascii=True))


if __name__ == "__main__":
    main()
