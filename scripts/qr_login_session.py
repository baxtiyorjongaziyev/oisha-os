import os
import asyncio

# Python-dotenv ni avtomatik o'rnatish uchun
try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("O'rnatilmoqda: python-dotenv...")
    os.system("pip install python-dotenv")
    from dotenv import load_dotenv, set_key

try:
    import qrcode
    import PIL
except ImportError:
    print("O'rnatilmoqda: qrcode[pil]...")
    os.system("pip install qrcode[pil] pillow")
    import qrcode

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print("O'rnatilmoqda: telethon...")
    os.system("pip install telethon")
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
TG_2FA_PASSWORD = os.getenv("TG_2FA_PASSWORD")

if not API_ID or not API_HASH:
    print("XATOLIK: .env faylida API_ID yoki API_HASH topilmadi!")
    exit(1)

async def main():
    client = TelegramClient(StringSession(), int(API_ID), API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        print("Siz allaqachon tizimga kirgansiz. Sessiya yangilanmoqda...")
        session_string = client.session.save()
    else:
        print("\nQR kod yuklanmoqda... Kuting...\n")
        qr = await client.qr_login()
        
        # QR kodni rasm sifatida saqlash
        qr_obj = qrcode.QRCode(border=2)
        qr_obj.add_data(qr.url)
        qr_obj.make(fit=True)
        
        img_path = r"C:\Users\baxti\.gemini\antigravity\brain\155b1371-b8f6-4b84-ba30-6924be5f1441\telegram_qr.png"
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        qr_img = qr_obj.make_image(fill_color="black", back_color="white")
        qr_img.save(img_path)
        
        print(f"QR kod rasm sifatida saqlandi: {img_path}")
        print("\n" + "="*50)
        print("TELEGRAM QR KOD:")
        try:
            qr_obj.print_ascii(invert=True)
        except Exception:
            pass
        print("="*50 + "\n")
        print("QR_READY")
        
        # Tasdiqlanishini kutish (180 soniya)
        try:
            await qr.wait(timeout=180)
        except asyncio.TimeoutError:
            print("QR kod muddati tugadi!")
            return
        except SessionPasswordNeededError:
            if TG_2FA_PASSWORD:
                print("2FA parol orqali ulanmoqda...")
                await client.sign_in(password=TG_2FA_PASSWORD)
            else:
                pwd = input("2FA Parolingizni kiriting: ").strip()
                await client.sign_in(password=pwd)
            
        session_string = client.session.save()
        me = await client.get_me()
        print(f"\n✅ Muvaffaqiyatli kirildi! Profil: {me.first_name} (@{me.username or 'username_yoq'})")
    
    # .env ni yangilash
    env_file = ".env"
    set_key(env_file, "USERBOT_SESSION_STRING", session_string)
    os.makedirs("data", exist_ok=True)
    with open("data/userbot_session_string.txt", "w", encoding="utf-8") as f:
        f.write(session_string.strip())

    print("🎉 Yangi session string .env va data/userbot_session_string.txt ga yozildi!")
    await client.disconnect()

if __name__ == "__main__":
    # Windows'da xatolik bermasligi uchun
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
