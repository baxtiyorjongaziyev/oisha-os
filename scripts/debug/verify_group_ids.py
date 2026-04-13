import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

api_id = int(os.getenv('API_ID', '0'))
api_hash = os.getenv('API_HASH', '')

async def find_groups():
    session_path = os.path.join(os.getcwd(), 'data', 'userbot_session')
    async with TelegramClient(session_path, api_id, api_hash) as client:
        print("Guruhlarni qidirish boshlandi... 👸🛡️")
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                # "Tez Natija" yoki "UMUMIY" so'zlarini qidirish
                if "Tez Natija" in dialog.name or "UMUMIY" in dialog.name:
                    print(f"Topildi: Nomi: '{dialog.name}' | ID: {dialog.id}")

if __name__ == "__main__":
    asyncio.run(find_groups())
