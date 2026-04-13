#!/usr/bin/env python3
"""
👸 OISHA: TEZ NATIJA 2/3/4/5 - XAVFSIZ Yig'ish (Yangi Session)
"""

import asyncio
import logging
import os
import random
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient, errors
from src.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SafeCollector")

SESSION_NAME = 'oisha_userbot'  # Mavjud avtorizatsiya qilingan session

GROUPS = [
    ('"TEZ NATIJA 5" UMUMIY', 'TN5'),
    ('"TEZ NATIJA 4" UMUMIY', 'TN4'),
    ('"TEZ NATIJA 3" UMUMIY', 'TN3'),
    ('"TEZ NATIJA 2" UMUMIY', 'TN2'),
]


async def safe_collect():
    """Faqat CSV fayllarga yig'ish."""
    
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    all_stats = {}
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            print("Avval: .venv_oi\\Scripts\\python scripts\\auth_telegram.py")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name}")
        print()
        print("⚠️  XAVFSIZ REJIM: Faqat CSV fayllarga yig'ish")
        print()
        
        for group_full_name, group_label in GROUPS:
            print("=" * 70)
            print(f'👸 {group_full_name}')
            print("=" * 70)
            
            target_group = None
            async for dialog in client.iter_dialogs():
                dialog_name = dialog.name or ""
                if f"tez natija {group_label[-1]}" in dialog_name.lower():
                    target_group = dialog
                    print(f"✅ Topildi: {dialog.name}")
                    break
            
            if not target_group:
                print(f'❌ {group_full_name} topilmadi!')
                continue
            
            with_phone = []
            without_phone = []
            
            print(f"📊 A'zolarni yig'ish...")
            print("-" * 70)
            
            async for user in client.iter_participants(target_group.id):
                if user.bot:
                    continue
                
                first_name = user.first_name or "NoName"
                last_name = user.last_name or ""
                username = user.username or ""
                phone = user.phone
                user_id = user.id
                
                if last_name:
                    csv_last_name = f"{last_name} {group_label} Gr"
                else:
                    csv_last_name = f"{group_label} Gr"
                
                full_name = f"{first_name} {csv_last_name}"
                
                if phone:
                    with_phone.append({
                        'Name': full_name,
                        'Given Name': first_name,
                        'Family Name': csv_last_name,
                        'Phone 1 - Value': phone,
                        'Phone 1 - Type': 'Mobile',
                        'Notes': f"@{username}" if username else f"{group_label} a'zosi",
                        'Labels': f'TEZ NATIJA {group_label[-1]}'
                    })
                    print(f"📱 {full_name} - {phone}")
                else:
                    without_phone.append({
                        'Name': full_name,
                        'Given Name': first_name,
                        'Family Name': csv_last_name,
                        'Notes': f"@{username}" if username else f"{group_label} a'zosi (ID: {user_id})",
                        'Labels': f'TEZ NATIJA {group_label[-1]}'
                    })
                    print(f"💬 {full_name} (@{username})")
                
                await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # CSV fayllar
            if with_phone:
                csv_phone = f'tn{group_label[-1]}_with_phone.csv'
                with open(csv_phone, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['Name', 'Given Name', 'Family Name', 'Phone 1 - Value', 'Phone 1 - Type', 'Notes', 'Labels']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(with_phone)
                print(f"\n📁 Telefon borlar: {csv_phone} ({len(with_phone)} ta)")
            
            if without_phone:
                csv_no_phone = f'tn{group_label[-1]}_no_phone.csv'
                with open(csv_no_phone, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['Name', 'Given Name', 'Family Name', 'Notes', 'Labels']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(without_phone)
                print(f"📁 Telefon yo'qlar: {csv_no_phone} ({len(without_phone)} ta)")
            
            all_stats[group_label] = {
                'with_phone': len(with_phone),
                'without_phone': len(without_phone),
                'total': len(with_phone) + len(without_phone)
            }
            
            print(f"\n📊 {group_label}: {len(with_phone)} telefon, {len(without_phone)} telefonsiz")
            await asyncio.sleep(2)
        
        # Yakuniy xulosa
        print("\n" + "=" * 70)
        print("✅ TUGADI!")
        print("=" * 70)
        total_all = sum(s['total'] for s in all_stats.values())
        print(f"📊 Jami: {total_all} ta kontakt")
        print("\n📁 CSV fayllar:")
        for label in ['TN2', 'TN3', 'TN4', 'TN5']:
            if os.path.exists(f'tn{label[-1]}_with_phone.csv'):
                print(f"   📱 tn{label[-1]}_with_phone.csv")
            if os.path.exists(f'tn{label[-1]}_no_phone.csv'):
                print(f"   💬 tn{label[-1]}_no_phone.csv")
        print("\n📱 Google Contacts: https://contacts.google.com → Import")
        print("=" * 70)
        
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("=" * 70)
    print("👸 OISHA: TEZ NATIJA 2/3/4/5 - XAVFSIZ Yig'ish")
    print("=" * 70)
    print()
    asyncio.run(safe_collect())
