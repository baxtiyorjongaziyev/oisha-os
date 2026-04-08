
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

async def find_tn5():
    try:
        api_id = int(env_dict['API_ID'])
        api_hash = env_dict['API_HASH']
        # Try both sessions
        sessions = [
            os.path.join(project_root, 'data', 'userbot_session'),
            os.path.join(project_root, 'userbot_session')
        ]
        
        for sess in sessions:
            print(f"Trying session: {sess}")
            client = TelegramClient(sess, api_id, api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                print(f"SUCCESS: Authorized with {sess}")
                async for dialog in client.iter_dialogs():
                    if 'TEZ NATIJA 5' in dialog.name.upper():
                        print(f"MATCH: {dialog.name} | ID: {dialog.id}")
                        participants = await client.get_participants(dialog.id, limit=0)
                        print(f"Total Participants: {participants.total}")
                await client.disconnect()
                return
            else:
                print(f"NOT AUTHORIZED: {sess}")
                await client.disconnect()

        print("No authorized session found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(find_tn5())
