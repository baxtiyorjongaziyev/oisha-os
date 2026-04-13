#!/usr/bin/env python3
"""
👸 OISHA: TEZ NATIJA 2/3/4/5 - XAVFSIZ Yig'ish (Spam Risk: Minimal)

FAqat CSV fayllarga yig'ish, Telegramga avtomatik qo'shmaslik.
Keyin o'zingiz xohlagancha qo'shasiz.
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
from src.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SafeCollector")

SESSION_NAME = 'oisha_userbot'

# Guruhlar ro'yxati
GROUPS = [
    ('"TEZ NATIJA 5" UMUMIY', 'TN5'),
    ('"TEZ NATIJA 4" UMUMIY', 'TN4'),
    ('"TEZ NATIJA 3" UMUMIY', 'TN3'),
    ('"TEZ NATIJA 2" UMUMIY', 'TN2'),
]


async def safe_collect():
    """Faqat CSV fayllarga yig'ish (Telegramga qo'shmaslik)."""
    
    db = Database()
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    
    all_stats = {}
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram avtorizatsiyasi yo'q!")
            return
        
        me = await client.get_me()
        print(f"✅ Telegram ulandi: {me.first_name}")
        print()
        print("⚠️  XAVFSIZ REJIM: Faqat CSV fayllarga yig'ish")
        print("    Telegram Contacts-ga avtomatik qo'shilmaydi!")
        print()
        
        for group_full_name, group_label in GROUPS:
            print("=" * 70)
            print(f'👸 {group_full_name}')
            print("=" * 70)
            
            # Guruhni qidirish
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
            
            # Ro'yxatlar
            with_phone = []
            without_phone = []
            
            print(f"📊 A'zolarni yig'ish... (Faqat o'qish, qo'shmaslik)")
            print("-" * 70)
            
            async for user in client.iter_participants(target_group.id):
                if user.bot:
                    continue
                
                first_name = user.first_name or "NoName"
                last_name = user.last_name or ""
                username = user.username or ""
                phone = user.phone
                user_id = user.id
                
                # Ism formati: "Ism Familya TN2 Gr"
                if last_name:
                    csv_last_name = f"{last_name} {group_label} Gr"
                else:
                    csv_last_name = f"{group_label} Gr"
                
                full_name = f"{first_name} {csv_last_name}"
                
                # Bazaga saqlash
                db.upsert_user(
                    user_id=user_id,
                    first_name=first_name,
                    last_name=csv_last_name,
                    username=username,
                    phone=phone or "",
                    role=f"Lead ({group_label})",
                    last_seen=None
                )
                
                # Ma'lumotlarni saqlash
                contact_data = {
                    'Name': full_name,
                    'Given Name': first_name,
                    'Family Name': csv_last_name,
                    'Phone 1 - Value': phone if phone else "",
                    'Phone 1 - Type': 'Mobile' if phone else "",
                    'Notes': f"@{username}" if username else f"{group_label} a'zosi (ID: {user_id})",
                    'Labels': f'TEZ NATIJA {group_label[-1]}',
                    'username': username,
                    'user_id': user_id
                }
                
                if phone:
                    with_phone.append(contact_data)
                    print(f"📱 {full_name} - {phone}")
                else:
                    without_phone.append(contact_data)
                    print(f"💬 {full_name} (@{username}) - telefon yo'q")
                
                # Xavfsiz delay (faqat o'qish uchun)
                await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # CSV fayllarni yaratish
            # 1. Telefon borlar uchun
            if with_phone:
                csv_phone = f'tn{group_label[-1]}_with_phone.csv'
                with open(csv_phone, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['Name', 'Given Name', 'Family Name', 'Phone 1 - Value', 'Phone 1 - Type', 'Notes', 'Labels']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for c in with_phone:
                        writer.writerow({
                            'Name': c['Name'],
                            'Given Name': c['Given Name'],
                            'Family Name': c['Family Name'],
                            'Phone 1 - Value': c['Phone 1 - Value'],
                            'Phone 1 - Type': c['Phone 1 - Type'],
                            'Notes': c['Notes'],
                            'Labels': c['Labels']
                        })
                print(f"\n📁 Telefon borlar: {csv_phone} ({len(with_phone)} ta)")
            
            # 2. Telefon yo'qlar uchun (qo'lda qo'shish uchun)
            if without_phone:
                csv_no_phone = f'tn{group_label[-1]}_no_phone.csv'
                with open(csv_no_phone, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['Name', 'Given Name', 'Family Name', 'Notes', 'Labels', 'Username', 'User ID']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for c in without_phone:
                        writer.writerow({
                            'Name': c['Name'],
                            'Given Name': c['Given Name'],
                            'Family Name': c['Family Name'],
                            'Notes': c['Notes'],
                            'Labels': c['Labels'],
                            'Username': c['username'],
                            'User ID': c['user_id']
                        })
                print(f"📁 Telefon yo'qlar: {csv_no_phone} ({len(without_phone)} ta)")
            
            all_stats[group_label] = {
                'with_phone': len(with_phone),
                'without_phone': len(without_phone),
                'total': len(with_phone) + len(without_phone)
            }
            
            print()
            print(f"📊 {group_label} NATIJA:")
            print(f"   📱 Telefon bilan: {len(with_phone)} ta")
            print(f"   💬 Telefonsiz: {len(without_phone)} ta")
            print(f"   📊 Jami: {len(with_phone) + len(without_phone)} ta")
            print()
            
            # Guruhlar o'rtasida tanaffus
            await asyncio.sleep(3)
        
        # Yakuniy xulosa
        print("=" * 70)
        print("✅ BARCHA GURUHLAR TUGADI!")
        print("=" * 70)
        print()
        
        total_all = 0
        for group_label, stats in all_stats.items():
            print(f"📊 {group_label}:")
            print(f"   📱 Telefon: {stats['with_phone']} ta")
            print(f"   💬 Telefonsiz: {stats['without_phone']} ta")
            print(f"   📊 Jami: {stats['total']} ta")
            total_all += stats['total']
            print()
        
        print("=" * 70)
        print(f"📊 HAMMASIBO'YICHA: {total_all} ta kontakt")
        print("=" * 70)
        print()
        print("📁 Yaratilgan CSV fayllar:")
        for group_label in ['TN2', 'TN3', 'TN4', 'TN5']:
            if os.path.exists(f'tn{group_label[-1]}_with_phone.csv'):
                print(f"   📱 tn{group_label[-1]}_with_phone.csv")
            if os.path.exists(f'tn{group_label[-1]}_no_phone.csv'):
                print(f"   💬 tn{group_label[-1]}_no_phone.csv")
        print()
        print("📱 Google Contacts-ga import:")
        print("   https://contacts.google.com → Import")
        print()
        print("💡 Eslatma: CSV fayllarni Google Contacts-ga import qiling.")
        print("   Telegram Contacts-ga qo'shish xavfsiz emas!")
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
    print("✅ Spam xavfi: MINIMAL (faqat o'qish)")
    print("❌ Telegramga avtomatik qo'shilmaydi")
    print("📁 Faqat CSV fayllarga yig'iladi")
    print()
    
    asyncio.run(safe_collect())
