import os
import asyncio
import sys
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
phone = '+998336450097'
password = 'Telegram0097' # User provided this earlier

async def main():
    if len(sys.argv) < 2:
        print("Error: Code argument missing")
        return
        
    code = sys.argv[1]
    
    # Read hash from file
    hash_path = 'data/auth_hash.txt'
    if not os.path.exists(hash_path):
        print("Error: Hash file missing. Run step 1 first.")
        return
        
    with open(hash_path, 'r') as f:
        phone_hash = f.read().strip()

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()
    
    try:
        # Step 2: Final Sign-In
        await client.sign_in(phone=phone, code=code, password=password, phone_code_hash=phone_hash)
        print("LOGIN_SUCCESSFUL")
        print("NEW_SESSION_STRING_START")
        print(client.session.save())
        print("NEW_SESSION_STRING_END")
    except Exception as e:
        print(f"ERROR: {e}")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
