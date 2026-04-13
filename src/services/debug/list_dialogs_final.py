import asyncio
from telethon import TelegramClient
from settings import settings

async def main():
    try:
        client = TelegramClient('research_session', settings.API_ID, settings.API_HASH)
        await client.connect()
        print("Connected.")
        dialogs = await client.get_dialogs(limit=100)
        found = False
        for d in dialogs:
            if 'Tez natija 5' in d.name or 'Jon Branding Team' in d.name:
                print(f"FOUND: {d.name} | ID: {d.id} | Type: {'Group' if d.is_group else 'Channel' if d.is_channel else 'Other'}")
                found = True
        if not found:
            print("Group not found in first 100 dialogs.")
        await client.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
