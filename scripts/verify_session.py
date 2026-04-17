import asyncio
from telethon import TelegramClient
from src.settings import settings

async def main():
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    
    session_path = 'data/oisha_user.session'
    import os
    print(f"DEBUG: Checking {session_path}, exists: {os.path.exists(session_path)}, size: {os.path.getsize(session_path) if os.path.exists(session_path) else 0}")
    
    client = TelegramClient('data/oisha_user', api_id, api_hash)
    await client.connect() # Connect first
    
    if not await client.is_user_authorized():
        print("DEBUG: Client NOT authorized. Check session file integrity.")
    else:
        me = await client.get_me()
        print(f"LOGIN_VERIFIED: {me.first_name} (@{me.username})")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
