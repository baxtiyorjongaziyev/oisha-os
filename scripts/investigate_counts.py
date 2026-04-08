
import asyncio
import os
import sys

project_root = r"c:\Users\baxti\playground\oisha-os"
sys.path.append(project_root)

# Manually read .env
env_lines = open(os.path.join(project_root, '.env')).readlines()
env_dict = {}
for line in env_lines:
    if '=' in line:
        k, v = line.strip().split('=', 1)
        env_dict[k] = v

from telethon import TelegramClient

async def list_all_tn5_matches():
    try:
        api_id = int(env_dict['API_ID'])
        api_hash = env_dict['API_HASH']
        session_path = os.path.join(project_root, 'data', 'userbot_session')
        
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            print("Not authorized.")
            return

        print("--- Listing all matches for 'TEZ NATIJA 5' ---")
        async for dialog in client.iter_dialogs():
            if 'TEZ NATIJA 5' in dialog.name.upper():
                count = 0
                try:
                    participants = await client.get_participants(dialog.id, limit=0)
                    count = participants.total
                except:
                    pass
                print(f"Name: {dialog.name} | ID: {dialog.id} | UI Count?: {getattr(dialog.entity, 'participants_count', 'N/A')} | API Count: {count}")
        
        await client.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_all_tn5_matches())
