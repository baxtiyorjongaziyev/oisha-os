import os
import asyncio
from dotenv import load_dotenv, set_key
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

async def main():
    phone = (os.getenv("TG_PHONE") or "+998336450097").strip("'\"").strip()
    pwd = (os.getenv("TG_2FA_PASSWORD") or "Tg0097").strip("'\"").strip()
    
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    print(f"Raqamga kod yuborilmoqda: {phone}")
    sent = await client.send_code_request(phone)
    print(f"KOD_YUBORILDI_KUTILMOQDA (hash: {sent.phone_code_hash})")
    
    code = input("Telegram kodini kiriting: ").strip()
    try:
        await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
    except Exception as e:
        if "Password" in str(type(e)) or "Password" in str(e):
            print("2FA parol kiritilmoqda...")
            await client.sign_in(password=pwd)
        else:
            raise e
    
    session_str = client.session.save()
    set_key(".env", "USERBOT_SESSION_STRING", session_str)
    os.makedirs("data", exist_ok=True)
    with open("data/userbot_session_string.txt", "w", encoding="utf-8") as f:
        f.write(session_str.strip())
    
    me = await client.get_me()
    print(f"[SUCCESS] Login OK: {me.first_name} (@{me.username})")
    await client.disconnect()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())


