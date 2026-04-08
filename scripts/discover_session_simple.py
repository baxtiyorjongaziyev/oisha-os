import asyncio
import os
import sys
from telethon import TelegramClient

# HARDCODED for discovery
API_ID = 30643078
API_HASH = 'e5850001c1d86ac0fb439fbd8319cb7f'

async def find_active_session():
    # List of common session files to check
    files = [f for f in os.listdir('.') if f.endswith('.session')]
    if os.path.exists('data'):
        files += [os.path.join('data', f) for f in os.listdir('data') if f.endswith('.session')]
    
    print(f"🔍 Found {len(files)} session files to test.")
    
    for full_path in files:
        session_name = full_path.replace('.session', '')
        print(f"Testing {full_path}...")
        
        client = TelegramClient(session_name, API_ID, API_HASH)
        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✅ AUTHORIZED: {full_path} (User: {me.first_name})")
                return session_name
            else:
                print(f"❌ UNAUTHORIZED: {full_path}")
        except Exception as e:
            print(f"⚠️ ERROR {full_path}: {e}")
        finally:
            await client.disconnect()
            
    return None

if __name__ == "__main__":
    result = asyncio.run(find_active_session())
    if result:
        print(f"\n👸 [RESULT] Use this path: {result}")
    else:
        print("\n❌ [RESULT] No authorized sessions. Fresh login needed!")
