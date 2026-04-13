import asyncio
import os
import json
import logging
import sys

# Add project root to path
sys.path.append(os.getcwd())

from telethon import TelegramClient
from src.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def scan_jamoa_roles():
    """'Princess Safety' (Jamoa) a'zolarini va rollarini aniqlash."""
    print("🔍 Oisha-OS: Jamoa Skaneri ishga tushirildi... 👸🛡️")
    
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ ERROR: Userbot unauthorized.")
            return

        group_id = -1001550503024 # 'Princess Safety' (Jamoa)
        print(f"📈 Guruh (ID: {group_id}) a'zolarini skanerlash boshlandi...")
        
        roles = []
        async for participant in client.iter_participants(group_id):
            role_type = "Member"
            p_class = participant.participant.__class__.__name__
            if "Admin" in p_class or "Creator" in p_class:
                role_type = "Admin"
                
            full_name = f"{participant.first_name} {participant.last_name or ''}".strip()
            roles.append({
                'id': participant.id,
                'name': full_name,
                'username': participant.username,
                'role': role_type,
                'class': p_class
            })
            
        # JSON fayliga saqlash (Mutloq yo'l orqali)
        output_file = r"c:\Users\baxti\playground\oisha-os\data\jamoa_roles.json"
        
        data_dir = os.path.dirname(output_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(roles, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Skanerlash yakunlandi. {len(roles)} ta a'zo {output_file} fayliga saqlandi. 👸🛡️🎯")

    except Exception as e:
        logger.error(f"[SCAN FATAL] {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(scan_jamoa_roles())
