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
        qr_img = qrcode.make(qr.url)
        img_path = r"C:\Users\baxti\.gemini\antigravity\brain\358b12b0-fe93-4921-865a-e1952af1a02f\qr.png"
        qr_img.save(img_path)
        
        print(f"QR kod saqlandi: {img_path}")
        print("QR_READY")
        
        # Tasdiqlanishini kutish
        try:
            await qr.wait(timeout=120)
        except asyncio.TimeoutError:
            print("QR kod muddati tugadi!")
            return
        except SessionPasswordNeededError:
            if TG_2FA_PASSWORD:
                print("2FA parol orqali ulanmoqda...")
                await client.sign_in(password=TG_2FA_PASSWORD)
            else:
                print("XATOLIK: 2FA parol kerak, lekin TG_2FA_PASSWORD berilmagan!")
                return
            
        session_string = client.session.save()
        me = await client.get_me()
        print(f"\n✅ Muvaffaqiyatli kirildi! Profil: {me.first_name} (@{me.username})")
    
    # .env ni yangilash
    env_file = ".env"
    set_key(env_file, "USERBOT_SESSION_STRING", session_string)
    set_key(env_file, "TELEGRAM_MCP_SESSION_STRING", session_string)
    
    print("🎉 Yangi session string .env fayliga avtomatik tarzda yozildi!")
    await client.disconnect()

if __name__ == "__main__":
    # Windows'da xatolik bermasligi uchun
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
