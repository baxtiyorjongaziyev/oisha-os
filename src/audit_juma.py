import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime, timezone
from src.settings import settings
from src.database import Database


async def audit_juma():
    session_string = (
        settings.USERBOT_SESSION_STRING.get_secret_value()
        if settings.USERBOT_SESSION_STRING
        else None
    )

    if session_string:
        print("[AUDIT] Using USERBOT_SESSION_STRING for authentication.")
        client = TelegramClient(
            StringSession(session_string),
            settings.API_ID,
            settings.API_HASH,
        )
    else:
        print(
            "[AUDIT] No session string found. Using file-based session: data/userbot_session"
        )
        client = TelegramClient(
            "data/userbot_session", settings.API_ID, settings.API_HASH
        )

    await client.start()

    today = datetime.now(timezone.utc).date()
    today_str = today.strftime("%Y-%m-%d")
    count = 0
    sent_ids = []

    print(f"[AUDIT] Scanning recent sent messages (Today: {today_str})...")

    # We scan the most recent 1000 messages from the userbot
    async for msg in client.iter_messages(None, limit=1000):
        if msg.out and msg.date.date() == today:
            text = msg.text or ""
            if "Juma" in text and ("muborak" in text.lower() or "ayyom" in text.lower()):
                count += 1
                if msg.peer_id:
                    # Handle different Peer types
                    try:
                        p_id = msg.peer_id.user_id
                        sent_ids.append(p_id)
                    except AttributeError:
                        pass

    print(f"[AUDIT] Total unique Juma greetings sent today: {count}")

    # Sync to DB to avoid duplicates
    if sent_ids:
        db = Database()
        await db.init_instance()
        conn = await db.get_connection()

        for s_id in sent_ids:
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO juma_sent_logs (user_id, run_date) VALUES (?, ?)",
                    (s_id, today_str),
                )
            except Exception as e:
                print(f"[AUDIT] DB insert error for {s_id}: {e}")

        await conn.commit()
        await db.close()
        print(f"[AUDIT] Synced {len(sent_ids)} IDs to juma_sent_logs.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(audit_juma())
