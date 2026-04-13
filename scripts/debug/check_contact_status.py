
from telethon import TelegramClient, functions, types
import os
from dotenv import load_dotenv

# Load env
load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
# Use the large session
session_path = r"c:\Users\baxti\playground\oisha-os\data\userbot_session"

async def main():
    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()
    
    # Get the group
    group_entity = await client.get_entity('https://t.me/+P3O6vN7YwKthMmEy')
    print(f"Group: {group_entity.title}")
    
    # Get 5 participants
    participants = await client.get_participants(group_entity, limit=5)
    
    for p in participants:
        print(f"User: {p.first_name} (@{p.username}) - Contact: {p.contact} - Mutual: {p.mutual_contact}")
        
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
