
import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_path = r"c:\Users\baxti\playground\oisha-os\data\userbot_session"

async def main():
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("ERROR: Not authorized")
            return
        
        print("Searching for 'Tez Natija 5' in your chats...")
        found = False
        async for dialog in client.iter_dialogs():
            if "Tez Natija 5" in dialog.name:
                print(f"FOUND_GROUP: Name='{dialog.name}', ID={dialog.id}, AccessHash={dialog.entity.access_hash if hasattr(dialog.entity, 'access_hash') else 'N/A'}")
                found = True
                
                print(f"Fetching participants for {dialog.name}...")
                participants = await client.get_participants(dialog.entity)
                print(f"SUCCESS: Found {len(participants)} members.")
                # We won't add them yet, just verifying we can see them.
                break
        
        if not found:
            print("ERROR: 'Tez Natija 5' group not found in your current chat list.")

    except Exception as e:
        print(f"GLOBAL ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
