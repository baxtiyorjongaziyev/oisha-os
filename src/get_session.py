import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load API credentials from .env
load_dotenv()
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

if not api_id or not api_hash:
    print("XATO: .env faylida API_ID yoki API_HASH topilmadi!")
    exit(1)

async def main():
    print("--- Oisha-OS Sessiya Generatori ---")
    print("Hozir sizdan telefon raqami, kod va (agar bo'lsa) 2FA paroli so'raladi.")
    
    # Using StringSession to get a portable session string
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    
    await client.start()
    
    session_string = client.session.save()
    
    print("\n" + "="*50)
    print("MUVAFFAQIYATLI KIRILDINGIZ!")
    print("Quyidagi uzun tekstni nusxalab (copy), chatga tashlang:")
    print("\n" + session_string + "\n")
    print("="*50)
    
    await client.disconnect()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
