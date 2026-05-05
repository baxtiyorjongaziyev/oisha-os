import asyncio
from telethon import TelegramClient
from datetime import datetime, timezone
from src.settings import settings
import sqlite3


async def audit_juma():
    client = TelegramClient("data/userbot_session", settings.API_ID, settings.API_HASH)
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
            if "Juma ayyomingiz muborak bo'lsin" in text:
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
        conn = sqlite3.connect("data/bot.db")
        cursor = conn.cursor()
        for s_id in sent_ids:
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO juma_sent_logs (user_id, run_date) VALUES (?, ?)",
                    (s_id, today_str),
                )
            except:
                pass
        conn.commit()
        conn.close()
        print(f"[AUDIT] Synced {len(sent_ids)} IDs to juma_sent_logs.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(audit_juma())
