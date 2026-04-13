
import asyncio
import os
import sys

# Add the project root to sys.path
# Since this script is in c:\Users\baxti\playground\oisha-os\scripts\
project_root = r"c:\Users\baxti\playground\oisha-os"
sys.path.append(project_root)

from telethon import TelegramClient
from src.settings import settings

async def find_tn5():
    try:
        # Use the session file in data/ which is larger
        session_path = os.path.join(project_root, 'data', 'userbot_session')
        client = TelegramClient(session_path, settings.API_ID, settings.API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            print("Client is not authorized!")
            return

        print("Searching for 'Tez natija 5' in dialogs...")
        group_found = False
        async for dialog in client.iter_dialogs():
            if 'TEZ NATIJA 5' in dialog.name.upper():
                print(f"MATCH: {dialog.name} | ID: {dialog.id}")
                group_found = True
                try:
                    participants = await client.get_participants(dialog.id, limit=0)
                    print(f"Total Participants: {participants.total}")
                except Exception as ep:
                    print(f"Participant Error: {ep}")
        
        if not group_found:
             print("Group not found by 'TEZ NATIJA 5' name.")

        await client.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(find_tn5())
