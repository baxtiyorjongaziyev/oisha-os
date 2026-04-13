#!/usr/bin/env python3
"""Telegram Userbot Avtorizatsiyasi"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient
from src.settings import settings

async def main():
    print("=" * 60)
    print("📱 TELEGRAM AVTORIZATSIYA")
    print("=" * 60)
    print()
    print("1. Telefon raqamingizni kiriting (masalan: +998901234567)")
    print("2. Telegram dan kelgan kodni kiriting")
    print("3. Tayyor!")
    print()
    print("=" * 60)
    
    client = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH)
    
    try:
        await client.start()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            print()
            print("=" * 60)
            print(f"✅ AVTORIZATSIYA MUVAFFAQIYATLI!")
            print("=" * 60)
            print(f"👤 Ism: {me.first_name} {me.last_name or ''}")
            print(f"🆔 ID: {me.id}")
            print(f"📱 Username: @{me.username or 'yoq'}")
            print("=" * 60)
            print()
            print("Endi contactlarni saqlash mumkin!")
            print("Ishga tushirish: .venv_oi\\Scripts\\python scripts\\full_export.py")
            
    except Exception as e:
        print(f"❌ Xato: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
