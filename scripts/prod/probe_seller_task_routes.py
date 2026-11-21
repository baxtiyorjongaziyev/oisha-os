"""Read-only checks for seller task destinations; never start a userbot."""
import asyncio
import json
import sqlite3
import requests

from src.database import Database
from src.settings import settings
from aiogram import Bot


async def main():
    db = Database()
    token = settings.BOT_TOKEN
    token = token.get_secret_value() if hasattr(token, "get_secret_value") else token
    bot = Bot(token=token)
    try:
        secret = settings.OISHA_API_SECRET
        secret = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
        for username in ("RayxonJonbranding", "MumtozmaxalJonbranding", "jonbranding_assistant"):
            response = requests.get(
                f"http://127.0.0.1:8080/api/internal/mcp/messages/{username}",
                headers={"Authorization": f"Bearer {secret}"}, params={"limit": 10}, timeout=20,
            )
            if response.status_code == 200:
                incoming = [m for m in response.json().get("messages", []) if not m.get("is_out")]
                print(json.dumps({"live_username": username, "incoming_senders": [
                    {"id": m["sender_id"], "name": m["sender_name"]} for m in incoming[:1]
                ]}, ensure_ascii=False))
                for message in incoming[:1]:
                    try:
                        chat = await bot.get_chat(int(message["sender_id"]))
                        print(json.dumps({"bot_chat": {"id": chat.id, "username": chat.username, "type": chat.type}}))
                    except Exception as exc:
                        print(json.dumps({"live_username": username, "bot_chat_error": type(exc).__name__}))
            else:
                print(json.dumps({"live_username": username, "status": response.status_code}))
        local = sqlite3.connect("file:data/bot.db?mode=ro", uri=True)
        local.row_factory = sqlite3.Row
        local_rows = [dict(r) for r in local.execute(
            "SELECT user_id, first_name, username FROM users WHERE "
            "LOWER(username) LIKE '%rayxon%' OR LOWER(username) LIKE '%mumtoz%' "
            "OR LOWER(username) LIKE '%shahno%' OR LOWER(username) LIKE '%jonbranding_assistant%'"
        )]
        local.close()
        print(json.dumps({"local_candidates": local_rows}, ensure_ascii=False))
        for row in local_rows:
            try:
                chat = await bot.get_chat(int(row["user_id"]))
                print(json.dumps({"bot_chat": {"id": chat.id, "username": chat.username, "type": chat.type}}))
            except Exception as exc:
                print(json.dumps({"id": row["user_id"], "bot_chat_error": type(exc).__name__}))
        rows = await db.users._fetch_all(
            "SELECT user_id, first_name, username FROM users WHERE "
            "LOWER(username) LIKE '%rayxon%' OR LOWER(username) LIKE '%mumtoz%' "
            "OR LOWER(username) LIKE '%shahno%' OR LOWER(first_name) LIKE '%shahno%' "
            "OR LOWER(first_name) LIKE '%mumtoz%' OR LOWER(first_name) LIKE '%rayxon%'"
        )
        print(json.dumps({"candidates": rows}, ensure_ascii=False))
        for username in ("RayxonJonbranding", "MumtozmaxalJonbranding", "Shahnozzy"):
            row = await db.get_user_by_username(username)
            result = {"username": username, "db_user": row}
            if row:
                try:
                    chat = await bot.get_chat(int(row["user_id"]))
                    result["bot_chat"] = {"id": chat.id, "username": chat.username, "type": chat.type}
                except Exception as exc:
                    result["bot_chat_error"] = type(exc).__name__
            print(json.dumps(result, ensure_ascii=False))
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
