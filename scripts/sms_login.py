import os
import asyncio
from dotenv import load_dotenv, set_key
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

async def main():
    phone = os.getenv("TG_PHONE")
    code = os.getenv("TG_CODE")
    pwd = os.getenv("TG_2FA_PASSWORD")
    
    session_string = os.getenv("USERBOT_SESSION_STRING") or ""
    session_string = session_string.strip("'\"")
    client = TelegramClient(StringSession(session_string), int(API_ID), API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        print("ALLAQAQACHON_ULANILGAN")
        return

    if not code:
        # Kod yuborish
        print(f"Raqamga kod yuborilmoqda: {phone}")
        result = await client.send_code_request(phone)
        print(f"KOD_YUBORILDI {result.phone_code_hash}")
        set_key(".env", "USERBOT_SESSION_STRING", client.session.save())
        set_key(".env", "TG_HASH", result.phone_code_hash)
    else:
        # Kodni tasdiqlash
        print(f"Kodni tekshirish: {code}")
        try:
            hash_val = os.getenv("TG_HASH")
            hash_val = hash_val.strip("'\"") if hash_val else ""
            await client.sign_in(phone, code, phone_code_hash=hash_val)
        except Exception as e:
            if "SessionPasswordNeededError" in str(type(e)) or "Password" in str(type(e)):
                if pwd:
                    print("2FA parol kiritilmoqda...")
                    await client.sign_in(password=pwd)
                else:
                    print("XATOLIK: 2FA parol kerak!")
                    return
            else:
                raise e
        
        set_key(".env", "USERBOT_SESSION_STRING", client.session.save())
        # NOTE: TELEGRAM_MCP_SESSION_STRING must be a DEDICATED session, never
        # equal to USERBOT_SESSION_STRING (see CLAUDE.md). Generate it separately.
        me = await client.get_me()
        print(f"MUVAFFAQIYATLI: {me.first_name} (@{me.username})")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
