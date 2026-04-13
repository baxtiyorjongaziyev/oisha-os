
import os
import asyncio
from telethon import TelegramClient, functions, types
from telethon.tl.functions.messages import ImportChatInviteRequest
from dotenv import load_dotenv

load_dotenv(r"c:\Users\baxti\playground\oisha-os\.env")

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_path = r"c:\Users\baxti\playground\oisha-os\data\userbot_session"
invite_link = "https://t.me/+o2G_r5927vwyMGIy"
invite_hash = "o2G_r5927vwyMGIy"

async def main():
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("ERROR: Not authorized")
            return
        
        print(f"Resolving invite link: {invite_link}")
        try:
            # Try to get the entity directly
            entity = await client.get_entity(invite_link)
        except Exception as e:
            print(f"Could not get entity directly, trying to join: {e}")
            try:
                updates = await client(ImportChatInviteRequest(invite_hash))
                entity = updates.chats[0]
            except Exception as e2:
                print(f"Failed to join: {e2}")
                return

        print(f"Found entity: {entity.title} (ID: {entity.id})")
        
        print("Fetching group members...")
        participants = await client.get_participants(entity)
        print(f"Found {len(participants)} participants.")
        
        count_added = 0
        batch_size = 30
        for i in range(0, len(participants), batch_size):
            batch = participants[i:i + batch_size]
            for user in batch:
                if user.bot or user.is_self: continue
                
                name = f"TN5 {user.first_name or ''} {user.last_name or ''}".strip()
                try:
                    await client(functions.contacts.AddContactRequest(
                        id=user,
                        first_name=name,
                        last_name='',
                        phone='',
                        add_phone_privacy_exception=True
                    ))
                    count_added += 1
                except Exception:
                    pass
            
            print(f"Current progress: {min(i + batch_size, len(participants))}/{len(participants)}")
            await asyncio.sleep(3) # Anti-flood

        # Final verification
        result = await client(functions.contacts.GetContactsRequest(hash=0))
        tn5_contacts = [u for u in result.users if (u.first_name and u.first_name.startswith("TN5 "))]
        print(f"FINAL_RESULTS: Total={len(result.users)}, TN5_Prefix={len(tn5_contacts)}")

    except Exception as e:
        print(f"GLOBAL ERROR: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
