import asyncio
import os
import sys
from telethon import TelegramClient, errors
from src.settings import settings

async def main():
    print("[OISHA] Userbot Login Starting...")
    
    session_file = 'data/oisha_user_active' # Note: .session is appended by Telethon
    
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    phone = "998336450097"
    
    # 3. Get password from sys.argv
    password = sys.argv[1] if len(sys.argv) > 1 else "Telegram0097"

    print(f"Connecting for phone: {phone}...")
    
    client = TelegramClient(
        session_file, 
        api_id, 
        api_hash,
        device_model="Oisha-OS VM",
        system_version="Linux/Windows",
        app_version="1.0"
    )

    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            # 1. Send Code Request
            print(f"Requesting new code for {phone}...")
            sent_code = await client.send_code_request(phone)
            phone_code_hash = sent_code.phone_code_hash
            
            # 2. Ask User for Code via Stdout/Prompt (Interactive is better here for ONE step)
            print("Action: Enter the code from Telegram below.")
            user_code = input("CODE: ")
            
            try:
                await client.sign_in(phone, user_code, phone_code_hash=phone_code_hash)
            except errors.SessionPasswordNeededError:
                print(f"Password required. Using provided password.")
                await client.sign_in(password=password)
            except Exception as e:
                print(f"Sign-in error: {e}")
                return

        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"SUCCESS: Logged in as: {me.first_name}")
            print(f"SESSION_SAVED: {session_file}.session")
        else:
            print("FAILED: Client not authorized.")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
