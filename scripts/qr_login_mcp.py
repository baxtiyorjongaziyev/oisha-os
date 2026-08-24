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
    print("[*] Telegram client yaratilmoqda...", flush=True)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        print("[!] Allaqachon avtorizatsiyadan o'tilgan.", flush=True)
        session_str = client.session.save()
    else:
        print("[*] QR kod login boshlanmoqda...", flush=True)
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        
        while True:
            try:
                qr = await client.qr_login()
                img = qrcode.make(qr.url)
                img.save(QR_IMAGE_PATH)
                print(f"[+] QR kod yangilandi: {QR_IMAGE_PATH} (URL: {qr.url})", flush=True)
                print("[*] Skan qilish kutilmoqda (120s)...", flush=True)
                await qr.wait(timeout=120)
                print("[+] QR kod muvaffaqiyatli skan qilindi!", flush=True)
                break
            except asyncio.TimeoutError:
                print("[*] QR kod muddati tugadi, yangi QR kod olinmoqda...", flush=True)
                continue
            except SessionPasswordNeededError:
                print("[!] 2FA parol talab qilinmoqda...", flush=True)
                tg_pwd = os.getenv("TG_2FA_PASSWORD") or os.getenv("TELEGRAM_PASSWORD")
                if tg_pwd:
                    await client.sign_in(password=tg_pwd)
                else:
                    pwd = input("2FA_PAROLNI_KIRITING: ").strip()
                    await client.sign_in(password=pwd)
                break
            
        session_str = client.session.save()
        me = await client.get_me()
        print("\n" + "=" * 60, flush=True)
        print(f"✅ Muvaffaqiyatli ulandi: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', '')})", flush=True)
        print("=" * 60, flush=True)
    
    print("\nSESSION_STRING:", flush=True)
    print(session_str, flush=True)
    
    # Save locally
    out_file = r"data\telegram_mcp_session_string.txt"
    os.makedirs("data", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(session_str)
    print(f"[+] Lokal session saqlandi: {out_file}", flush=True)
    
    # Deploy to Oracle VM .env
    print("[*] Oracle VM .env fayliga TELEGRAM_MCP_SESSION_STRING yozilmoqda...", flush=True)
    cmd_env = f"sed -i 's|^TELEGRAM_MCP_SESSION_STRING=.*|TELEGRAM_MCP_SESSION_STRING={session_str}|' /home/ubuntu/oisha-os/.env"
    res = subprocess.run(["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", VM_HOST, cmd_env], capture_output=True, text=True)
    if res.returncode == 0:
        print("[+] Oracle VM .env muvaffaqiyatli yangilandi!", flush=True)
    else:
        print(f"[!] Oracle VM .env yangilashda xatolik: {res.stderr}", flush=True)
        
    await client.disconnect()
    print("[+] Tugallandi!", flush=True)

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
