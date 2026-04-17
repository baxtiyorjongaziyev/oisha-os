import asyncio
import csv
import os
from telethon import TelegramClient
from telethon.tl.functions.messages import ImportChatInviteRequest
from src.settings import settings

async def main():
    print("[OISHA] Group Member Scraper Starting...")
    
    # 1. Configuration
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    session_path = 'data/oisha_user_active'
    invite_link = "https://t.me/+YExImbVr5VMwMjE6"
    output_file = 'data/juma_outreach_list.csv'
    
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    
    if not await client.is_user_authorized():
        print("Error: Userbot not authorized. Run login script first.")
        return

    print(f"Connected as userbot.")
    
    try:
        # Join group if not already a member
        if '+' in invite_link:
            hash = invite_link.split('+')[-1]
            try:
                await client(ImportChatInviteRequest(hash))
                print("Successfully joined the group via invite link.")
            except Exception as e:
                print(f"Note: Already in group or join failed: {e}")

        # Get entity
        entity = await client.get_entity(invite_link)
        print(f"Scraping members from: {entity.title}")

        contacts = []
        # Get all members
        async for user in client.iter_participants(entity):
            if user.bot:
                continue
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else ""
            phone = user.phone or ""
            
            contacts.append({
                'name': name,
                'phone': phone,
                'username': username,
                'user_id': user.id
            })

        print(f"Extraction complete! Found {len(contacts)} members.")

        # Save to CSV
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'phone', 'username', 'user_id'])
            writer.writeheader()
            for c in contacts:
                writer.writerow(c)
        
        print(f"Saved {len(contacts)} contacts to {output_file}")

    except Exception as e:
        print(f"Scraping failed: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
