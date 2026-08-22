"""
Yangi USERBOT_SESSION_STRING yaratish.
Lokal kompyuterda bir marta ishga tushiring:

  pip install telethon python-dotenv
  export API_ID=... API_HASH=...   # https://my.telegram.org
  python scripts/generate_session_string.py

Natijada chiqadigan SESSION_STRING qiymatini
GitHub Secrets → USERBOT_SESSION_STRING ga joylashtiring.
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]


import sys
from telethon.errors import SessionPasswordNeededError

async def main() -> None:
    force_sms = "--force-sms" in sys.argv
    phone_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if phone_args:
        phone = phone_args[0]
    
    password = os.environ.get("TELEGRAM_PASSWORD", "")
    
    print(f"[*] API_ID: {API_ID}")
    print(f"[*] So'rov yuborilmoqda: {phone} (force_sms={force_sms})...")
    
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"[*] Telegram kod so'ralmoqda ({phone})...")
        sent_code = await client.send_code_request(phone, force_sms=force_sms)
        print(f"[+] Telegram javobi turi: {type(sent_code.type).__name__}")
        print(f"[+] Telefon code hash: {sent_code.phone_code_hash}")
        if hasattr(sent_code, "timeout") and sent_code.timeout:
            print(f"[+] Timeout: {sent_code.timeout}s")
        
        code = input("KODNI_KIRITING: ").strip()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=sent_code.phone_code_hash)
        except SessionPasswordNeededError:
            print(f"[*] 2FA parol ishlatilmoqda...")
            try:
                await client.sign_in(password=password)
            except Exception as e:
                print(f"[!] 2FA xatolik: {e}")
                pwd = input("PAROLNI_QAYTA_KIRITING: ").strip()
                await client.sign_in(password=pwd)

    me = await client.get_me()
    session_str = client.session.save()
    await client.disconnect()

    # Save to data/userbot_session_string.txt
    os.makedirs("data", exist_ok=True)
    with open("data/userbot_session_string.txt", "w", encoding="utf-8") as f:
        f.write(session_str)

    # Also update .env file
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            env_content = f.read()
        if "USERBOT_SESSION_STRING=" in env_content:
            import re
            env_content = re.sub(r"USERBOT_SESSION_STRING=.*", f"USERBOT_SESSION_STRING={session_str}", env_content)
        else:
            env_content += f"\nUSERBOT_SESSION_STRING={session_str}\n"
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("[+] .env fayli USERBOT_SESSION_STRING bilan yangilandi!")

    print("\n" + "=" * 60)
    print("✅ Login muvaffaqiyatli:", getattr(me, "first_name", ""), f"(@{getattr(me, 'username', '')})")
    print("=" * 60)
    print("\nSESSION_STRING:\n")
    print(session_str)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
