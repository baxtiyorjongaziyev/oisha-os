import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import sys
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]

async def main():
    if len(sys.argv) < 3:
        print("ERROR: Code and/or Password not provided.")
        return
    
    code = sys.argv[1].strip()
    password = sys.argv[2].strip()
    session_path = os.path.join("data", "userbot_session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"Finalizing sign-in for {PHONE} with code {code} and 2FA...")
        try:
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            await client.sign_in(password=password)
            print("AUTH_SUCCESS_WITH_2FA")
        except Exception as e:
            print(f"ERROR: {str(e)}")
    else:
        print("ALREADY_AUTHORIZED")
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
