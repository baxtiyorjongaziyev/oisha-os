#!/usr/bin/env python3
import sys
import os
import random
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, errors, functions

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.settings import settings

logging.basicConfig(level=logging.INFO, filename='sync_error.txt', format='%(asctime)s - %(levelname)s - %(message)s')
SESSION_NAME = 'oisha_userbot'

GROUPS_CONFIG = [
    ('tn2_with_phone.csv', 'TN2'), ('tn2_no_phone.csv', 'TN2'),
    ('tn3_with_phone.csv', 'TN3'), ('tn3_no_phone.csv', 'TN3'),
    ('tn4_with_phone.csv', 'TN4'), ('tn4_no_phone.csv', 'TN4'), ('tn4_no_phone_users.csv', 'TN4'),
    ('tn5_with_phone.csv', 'TN5'), ('tn5_no_phone.csv', 'TN5'),
]

PROCESSED_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'synced_contacts.txt')
SKIPPED_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'skipped_contacts.txt')

def get_processed():
    processed = set()
    for f_path in [PROCESSED_FILE, SKIPPED_FILE]:
        if os.path.exists(f_path):
            with open(f_path, 'r') as f:
                processed.update(line.strip() for line in f if line.strip())
    return processed

def mark_done(identifier, success=True):
    f_path = PROCESSED_FILE if success else SKIPPED_FILE
    with open(f_path, 'a') as f:
        f.write(f"{identifier}\n")

def normalize_phone(phone):
    if not phone: return ""
    clean = "".join(filter(str.isdigit, str(phone)))
    if not clean.startswith('998') and len(clean) == 9: clean = '998' + clean
    return '+' + clean if clean else ""

async def main():
    client = TelegramClient(SESSION_NAME, settings.API_ID, settings.API_HASH)
    processed_set = get_processed()
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Avtorizatsiya yo'q!")
            return
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 👸 OISHA ulandi. Ish boshlandi...")
        
        for csv_file_name, label in GROUPS_CONFIG:
            csv_path = os.path.join(os.path.dirname(__file__), '..', csv_file_name)
            if not os.path.exists(csv_path): continue
            
            import csv
            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                contacts = list(csv.DictReader(f))
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📂 {csv_file_name} ({len(contacts)} ta qator)")
            
            for row in contacts:
                phone_val = row.get('Phone 1 - Value', '')
                notes = row.get('Notes', '')
                phone = normalize_phone(phone_val)
                username = notes.split()[0].replace('@', '').strip() if notes and notes.startswith('@') else ""
                
                identifier = phone if phone else username
                if not identifier or identifier in processed_set: continue
                
                name = row.get('Name') or row.get('Given Name', 'NoName')
                
                try:
                    added = False
                    if phone:
                        contact = functions.contacts.InputPhoneContact(
                            client_id=random.randint(0, 2**31 - 1), phone=phone, 
                            first_name=name, last_name=f"{label} Gr"
                        )
                        res = await asyncio.wait_for(client(functions.contacts.ImportContactsRequest(items=[contact])), timeout=30)
                        if res.users:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {name} ({phone}) - Saqlandi")
                            mark_done(identifier, True)
                            added = True
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ℹ️ {name} ({phone}) - Yo'q")
                            mark_done(identifier, False)
                    
                    elif username:
                        try:
                            user = await asyncio.wait_for(client.get_input_entity(username), timeout=30)
                            await asyncio.wait_for(client(functions.contacts.AddContactRequest(
                                id=user, first_name=name, last_name=f"{label} Gr", phone=''
                            )), timeout=30)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {name} (@{username}) - Saqlandi")
                            mark_done(identifier, True)
                            added = True
                        except Exception:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ℹ️ {name} (@{username}) - Yo'q")
                            mark_done(identifier, False)
                    
                    processed_set.add(identifier)
                    await asyncio.sleep(random.randint(15, 25))
                    
                except errors.FloodWaitError as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ FLOOD: {e.seconds}s kutamiz...")
                    await asyncio.sleep(e.seconds + 30)
                except Exception as e:
                    logging.error(f"Error for {name}: {e}")
                    await asyncio.sleep(5)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
