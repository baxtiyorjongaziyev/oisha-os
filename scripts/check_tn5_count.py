from telethon import TelegramClient, functions, types
import os
import asyncio
from dotenv import load_dotenv

# Load env
load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_path = r"c:\Users\baxti\playground\oisha-os\data\userbot_session"

async def main():
    async with TelegramClient(session_path, api_id, api_hash) as client:
        print("Checking contacts...")
        result = await client(functions.contacts.GetContactsRequest(hash=0))
        
        # Filter contacts with our tag
        tn5_contacts = [u for u in result.users if hasattr(u, 'last_name') and u.last_name and "TN5 Gr" in u.last_name]
        
        print(f"Total contacts on account: {len(result.users)}")
        print(f"Total 'TN5 Gr' tagged contacts: {len(tn5_contacts)}")
        
        if tn5_contacts:
            print("\nLast 5 TN5 contacts found:")
            for u in tn5_contacts[-5:]:
                print(f"- {u.first_name} {u.last_name} (ID: {u.id})")
        else:
            print("\nNO 'TN5 Gr' contacts found!")

if __name__ == "__main__":
    asyncio.run(main())
