
import os
import asyncio
from telethon import TelegramClient, functions, types
from dotenv import load_dotenv

load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_path = r"c:\Users\baxti\playground\oisha-os\data\userbot_session"
group_id = -1001946370425  # Tez Natija 5

async def main():
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("ERROR: Not authorized")
            return
        
        print("Fetching group members...")
        participants = await client.get_participants(group_id)
        print(f"Found {len(participants)} participants.")
        
        # We will try groups of 50
        batch_size = 50
        for i in range(0, len(participants), batch_size):
            batch = participants[i:i + batch_size]
            input_contacts = []
            for user in batch:
                if user.bot or user.is_self: continue
                
                # Use ImportContactsRequest which is more 'forceful'
                # Even without phone, we can pass client_id (temporary)
                # But typically ImportContacts requires phone. 
                # If no phone, AddContactRequest is the ONLY way.
                # Let's try AddContactRequest again BUT with a different set of flags
                # or try focusing on those with usernames.
                
                name = f"TN5 {user.first_name or ''} {user.last_name or ''}".strip()
                try:
                    # Alternative: use 'username' if they have one
                    peer = user
                    await client(functions.contacts.AddContactRequest(
                        id=peer,
                        first_name=name,
                        last_name='',
                        phone='', # No phone available
                        add_phone_privacy_exception=True
                    ))
                except Exception as e:
                    pass
            
            print(f"Processed batch {i//batch_size + 1}")
            await asyncio.sleep(2) # Avoid aggressive rate limiting

        # Final verification
        result = await client(functions.contacts.GetContactsRequest(hash=0))
        tn5_contacts = [u for u in result.users if (u.first_name and u.first_name.startswith("TN5 "))]
        print(f"FINAL_TN5_COUNT: {len(tn5_contacts)}")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
