
from telethon import TelegramClient
import os
from dotenv import load_dotenv

# Load env
load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

sessions = [
    r"c:\Users\baxti\playground\oisha-os\data\oisha_session",
    r"c:\Users\baxti\playground\oisha-os\data\userbot_session",
    r"c:\Users\baxti\playground\oisha-os\data\userbot"
]

async def check_session(path):
    print(f"Checking session: {path}...", end="")
    if not os.path.exists(path + ".session"):
        print(" does not exist.")
        return
    client = TelegramClient(path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(" NOT AUTHORIZED")
            return
        me = await client.get_me()
        print(f" AUTH: {me.first_name} {me.last_name or ''} (@{me.username or 'no_user'}) ID: {me.id}")
    except Exception as e:
        print(f" ERROR: {str(e)}")
    finally:
        await client.disconnect()

async def main():
    for s in sessions:
        await check_session(s)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
