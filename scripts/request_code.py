import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")


async def main():
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()
    # Request code for our target phone
    result = await client.send_code_request("+998336450097")
    print(f"PHONE_CODE_HASH:{result.phone_code_hash}")
    print("CODE_SENT")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
