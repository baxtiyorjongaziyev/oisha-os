import os
import asyncio
import time
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
phone = os.getenv("TELEGRAM_PHONE")
password = os.getenv("TELEGRAM_PASSWORD")
code_file = "data/code.txt"

import logging

logging.basicConfig(level=logging.DEBUG)


async def main():
    if os.path.exists(code_file):
        os.remove(code_file)

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()

    print("REQUESTING_CODE...")
    result = await client.send_code_request(phone)
    phone_hash = result.phone_code_hash
    print("CODE_SENT. WAITING_FOR_FILE...")

    # Poll for code.txt
    start_time = time.time()
    code = None
    while time.time() - start_time < 300:  # 5 minute timeout
        if os.path.exists(code_file):
            with open(code_file, "r") as f:
                code = f.read().strip()
            if code:
                break
        await asyncio.sleep(0.5)

    if not code:
        print("TIMEOUT_OR_EMPTY_CODE")
        await client.disconnect()
        return

    print(f"CODE_RECEIVED:{code}. SIGNING_IN...")
    try:
        await client.sign_in(
            phone=phone, code=code, password=password, phone_code_hash=phone_hash
        )
        print("POLLING_SUCCESS")
        print("NEW_SESSION_STRING_START")
        print(client.session.save())
        print("NEW_SESSION_STRING_END")
    except Exception as e:
        print(f"ERROR: {e}")

    await client.disconnect()
    if os.path.exists(code_file):
        os.remove(code_file)


if __name__ == "__main__":
    asyncio.run(main())
