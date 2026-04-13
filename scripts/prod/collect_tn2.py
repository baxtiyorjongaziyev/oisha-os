#!/usr/bin/env python3
"""
👸 OISHA: TEZ NATIJA 2 - Xavfsiz Yig'ish
"""
import asyncio, csv, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from telethon import TelegramClient
from src.settings import settings

async def collect_tn2():
    client = TelegramClient('oisha_userbot', settings.API_ID, settings.API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Avtorizatsiya yo'q!")
            return
        
        print("🔍 TEZ NATIJA 2 qidirilmoqda...")
        target = None
        async for dialog in client.iter_dialogs():
            if "tez natija 2" in dialog.name.lower():
                target = dialog
                print(f"✅ Topildi: {dialog.name}")
                break
        
        if not target:
            print("❌ Guruh topilmadi!")
            return
        
        with_phone, without_phone = [], []
        
        async for user in client.iter_participants(target.id):
            if user.bot:
                continue
            
            first = user.first_name or "NoName"
            last = user.last_name or ""
            username = user.username or ""
            phone = user.phone
            
            last_name = f"{last} TN2 Gr" if last else "TN2 Gr"
            full = f"{first} {last_name}"
            
            if phone:
                with_phone.append({
                    'Name': full, 'Given Name': first, 'Family Name': last_name,
                    'Phone 1 - Value': phone, 'Phone 1 - Type': 'Mobile',
                    'Notes': f"@{username}" if username else "TN2", 'Labels': 'TEZ NATIJA 2'
                })
                print(f"📱 {full} - {phone}")
            else:
                without_phone.append({
                    'Name': full, 'Given Name': first, 'Family Name': last_name,
                    'Notes': f"@{username}" if username else "TN2", 'Labels': 'TEZ NATIJA 2'
                })
                print(f"💬 {full}")
            
            await asyncio.sleep(random.uniform(0.3, 0.7))
        
        # CSV
        if with_phone:
            with open('tn2_with_phone.csv', 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['Name', 'Given Name', 'Family Name', 'Phone 1 - Value', 'Phone 1 - Type', 'Notes', 'Labels'])
                w.writeheader()
                w.writerows(with_phone)
            print(f"\n📁 tn2_with_phone.csv: {len(with_phone)} ta")
        
        if without_phone:
            with open('tn2_no_phone.csv', 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['Name', 'Given Name', 'Family Name', 'Notes', 'Labels'])
                w.writeheader()
                w.writerows(without_phone)
            print(f"📁 tn2_no_phone.csv: {len(without_phone)} ta")
        
        print(f"\n✅ TN2: {len(with_phone)} telefon, {len(without_phone)} telefonsiz")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("=" * 50)
    print("👸 OISHA: TEZ NATIJA 2")
    print("=" * 50)
    asyncio.run(collect_tn2())
