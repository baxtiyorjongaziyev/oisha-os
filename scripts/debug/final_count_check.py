
import os
import asyncio
from telethon import TelegramClient, functions
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
        
        result = await client(functions.contacts.GetContactsRequest(hash=0))
        print(f"DEBUG_CONTACT_COUNT: {len(result.users)}")
        
        # Also check if any have the prefix 'TN5 '
        tn5_contacts = [u for u in result.users if (u.first_name and u.first_name.startswith("TN5 "))]
        print(f"DEBUG_TN5_COUNT: {len(tn5_contacts)}")
        
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
