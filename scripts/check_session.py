import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "30643078"))
API_HASH = os.environ.get("API_HASH", "e5850001c1d86ac0fb439fbd8319cb7f")

async def main():
    session_file = "userbot_session"
    if os.path.exists(f"{session_file}.session"):
        print(f"[*] Found {session_file}.session ({os.path.getsize(session_file + '.session')} bytes)")
        client = TelegramClient(session_file, API_ID, API_HASH)
        try:
            await client.connect()
            auth = await client.is_user_authorized()
            print(f"[*] Is SQLite session authorized: {auth}")
            if auth:
                me = await client.get_me()
                print(f"[+] Logged in as: {me.first_name} (@{getattr(me, 'username', '')}) ID:{me.id} Phone:{me.phone}")
                str_session = StringSession.save(client.session)
                print(f"[+] Converted StringSession: {str_session}")
            await client.disconnect()
        except Exception as e:
            print(f"[!] Error testing SQLite session: {e}")
    else:
        print("[*] No userbot_session.session file found.")

    if os.path.exists("data/userbot_session_string.txt"):
        with open("data/userbot_session_string.txt", "r") as f:
            saved_str = f.read().strip()
        if saved_str:
            print(f"[*] Testing data/userbot_session_string.txt ({len(saved_str)} chars)...")
            client = TelegramClient(StringSession(saved_str), API_ID, API_HASH)
            try:
                await client.connect()
                auth = await client.is_user_authorized()
                print(f"[*] Is saved StringSession authorized: {auth}")
                if auth:
                    me = await client.get_me()
                    print(f"[+] Logged in as: {me.first_name} (@{getattr(me, 'username', '')}) ID:{me.id}")
                await client.disconnect()
            except Exception as e:
                print(f"[!] Error testing StringSession: {e}")

if __name__ == "__main__":
    asyncio.run(main())
