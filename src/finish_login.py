import os
import asyncio
import sys
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

async def main():
    phone = os.getenv('TELEGRAM_PHONE')
    code = os.getenv('TELEGRAM_CODE')
    hash = os.getenv('TELEGRAM_HASH')
    password = os.getenv('TELEGRAM_PASSWORD')
    
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()
    
    try:
        await client.sign_in(phone=phone, code=code, password=password, phone_code_hash=hash)
        print("LOGIN_SUCCESSFUL")
        print("NEW_SESSION_STRING_START")
        print(client.session.save())
        print("NEW_SESSION_STRING_END")
    except errors.SessionPasswordNeededError:
        # Should not happen as we provided password, but for completeness
        print("ERROR: PASSWORD_NEEDED")
    except Exception as e:
        print(f"ERROR: {e}")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
