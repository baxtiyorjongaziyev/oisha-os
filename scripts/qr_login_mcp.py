import os
import sys
import subprocess
import asyncio
import qrcode
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

API_ID = 30643078
API_HASH = "e5850001c1d86ac0fb439fbd8319cb7f"

ARTIFACT_DIR = r"C:\Users\baxti\.gemini\antigravity\brain\71f43ff6-5a84-4651-83e5-10160585a93e"
QR_IMAGE_PATH = os.path.join(ARTIFACT_DIR, "telegram_qr.png")
SSH_KEY = r"C:\Users\baxti\.ssh\oracle_free_tier_ed25519"
VM_HOST = "ubuntu@163.192.10.104"

async def main():
    print("[*] Telegram client yaratilmoqda...")
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        print("[!] Allaqachon avtorizatsiyadan o'tilgan.")
        session_str = client.session.save()
    else:
        print("[*] QR kod login so'ralmoqda...")
        qr = await client.qr_login()
        
        # QR rasm saqlash
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        img = qrcode.make(qr.url)
        img.save(QR_IMAGE_PATH)
        print(f"[+] QR kod rasm sifatida saqlandi: {QR_IMAGE_PATH}")
        print(f"[+] QR URL: {qr.url}")
        print("[*] QR_READY_FOR_SCAN")
        
        try:
            await qr.wait(timeout=180)
        except asyncio.TimeoutError:
            print("[X] QR kod muddati tugadi!")
            await client.disconnect()
            return
        except SessionPasswordNeededError:
            print("[!] 2FA parol talab qilinmoqda...")
            # If 2FA password exists in env
            tg_pwd = os.getenv("TG_2FA_PASSWORD") or os.getenv("TELEGRAM_PASSWORD")
            if tg_pwd:
                await client.sign_in(password=tg_pwd)
            else:
                pwd = input("2FA_PAROLNI_KIRITING: ").strip()
                await client.sign_in(password=pwd)
            
        session_str = client.session.save()
        me = await client.get_me()
        print("\n" + "=" * 60)
        print(f"✅ Muvaffaqiyatli ulandi: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', '')})")
        print("=" * 60)
    
    print("\nSESSION_STRING:")
    print(session_str)
    
    # Save locally
    out_file = r"data\telegram_mcp_session_string.txt"
    os.makedirs("data", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(session_str)
    print(f"[+] Lokal session saqlandi: {out_file}")
    
    # Deploy to Oracle VM .env
    print("[*] Oracle VM .env fayliga TELEGRAM_MCP_SESSION_STRING yozilmoqda...")
    cmd_env = f"sed -i 's|^TELEGRAM_MCP_SESSION_STRING=.*|TELEGRAM_MCP_SESSION_STRING={session_str}|' /home/ubuntu/oisha-os/.env"
    res = subprocess.run(["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", VM_HOST, cmd_env], capture_output=True, text=True)
    if res.returncode == 0:
        print("[+] Oracle VM .env muvaffaqiyatli yangilandi!")
    else:
        print(f"[!] Oracle VM .env yangilashda xatolik: {res.stderr}")
        
    await client.disconnect()
    print("[+] Tugallandi!")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
