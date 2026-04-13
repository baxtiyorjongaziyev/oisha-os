
import os
import asyncio
from telethon import TelegramClient, functions, types
from dotenv import load_dotenv

# Load env
load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

# Target the BIG session (598KB) which is likely the user's main account
SESSION_PATH = r"c:\Users\baxti\playground\oisha-os\data\userbot_session"
GROUP_LINK = "https://t.me/+P3O6vN7YwKthMmEy"
PREFIX = "TN5 "

async def main():
    print(f"Starting Refined Mass Sync using session: {SESSION_PATH}")
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("ERROR: Session is not authorized. Please login manually.")
            return
        
        me = await client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username})")
        
        # Resolve group
        try:
            group = await client.get_entity(GROUP_LINK)
            print(f"Target Group: {group.title}")
        except Exception as e:
            print(f"Could not find group: {e}")
            return
            
        # Get participants
        participants = await client.get_participants(group)
        print(f"Found {len(participants)} participants.")
        
        # Prepare contacts to import
        # Telegram ImportContactsRequest takes a list of InputPhoneContact
        # But if we don't have phone numbers, we must use AddContactRequest for each.
        # HOWEVER, AddContactRequest requires an InputUser.
        
        count = 0
        errors = 0
        
        for p in participants:
            if p.is_self or p.bot:
                continue
                
            # If they are already a contact, skip (optional, but safer to re-add with prefix)
            # if p.contact: continue
            
            first_name = f"{PREFIX}{p.first_name or 'User'}"
            last_name = p.last_name or ""
            
            try:
                # We use AddContactRequest which is the standard 'Add to Contacts'
                # ensure we pass the full peer (access_hash is included in 'p' if we got it from get_participants)
                await client(functions.contacts.AddContactRequest(
                    id=p,
                    first_name=first_name,
                    last_name=last_name,
                    phone='', # We don't have phones usually in groups
                    add_phone_privacy_exception=True
                ))
                count += 1
                if count % 10 == 0:
                    print(f"Progress: {count} contacts added...")
                await asyncio.sleep(0.5) # Avoid flood
            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"Error adding {p.id}: {e}")
        
        print(f"DONE! SUCCESSFULLY ADDED {count} CONTACTS.")
        print(f"ERRORS: {errors}")
        
    except Exception as e:
        print(f"Global error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
