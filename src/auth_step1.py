import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
phone = "+998336450097"


async def main():
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()
    # Request code
    result = await client.send_code_request(phone)
    # Save hash to file for step 2
    os.makedirs("data", exist_ok=True)
    with open("data/auth_hash.txt", "w") as f:
        f.write(result.phone_code_hash)
    print(f"PHONE_CODE_HASH_SAVED:{result.phone_code_hash}")
    print("CODE_SENT_TO_USER")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
