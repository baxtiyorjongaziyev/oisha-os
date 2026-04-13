import asyncio
from telethon import TelegramClient
from settings import settings

async def search_group():
    client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Error: User not authorized")
        return

    print("Searching for 'Tez natija 5' in dialogs...")
    async for dialog in client.iter_dialogs():
        if 'Tez natija 5' in dialog.name:
            print(f"Found: {dialog.name} (ID: {dialog.id})")
            
            # Count participants
            try:
                participants = await client.get_participants(dialog.id, limit=0)
                print(f"Total Participants: {participants.total}")
            except Exception as e:
                print(f"Could not fetch participants for {dialog.name}: {e}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(search_group())
