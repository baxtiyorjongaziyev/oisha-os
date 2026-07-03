import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load credentials
load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

if not api_id or not api_hash:
    print("Error: API_ID or API_HASH not found in .env")
    exit(1)

client = TelegramClient(StringSession(), int(api_id), api_hash)


async def main():
    print("Starting interactive login...")
    # This will prompt for phone, code, and password on the standard input
    await client.start()
    print("\nLOGIN SUCCESSFUL!")
    print("NEW_SESSION_STRING_START")
    print(client.session.save())
    print("NEW_SESSION_STRING_END")
    await client.disconnect()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
