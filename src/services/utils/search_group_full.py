import asyncio
from telethon import TelegramClient
from settings import settings


async def main():
    try:
        client = TelegramClient("userbot_session", settings.API_ID, settings.API_HASH)
        await client.connect()
        print("Connected.")

        target_name = '"TEZ NATIJA 5" UMUMIY'
        print(f"Searching for: {target_name}")

        async for dialog in client.iter_dialogs():
            if target_name.upper() in dialog.name.upper():
                print(f"FOUND: {dialog.name} | ID: {dialog.id}")

                # Try to get participants count
                try:
                    participants = await client.get_participants(dialog.id, limit=0)
                    print(f"Total Participants: {participants.total}")
                except Exception as ep:
                    print(f"Could not fetch participant count: {ep}")

                break
        else:
            print("Group not found. Listing potential matches:")
            async for d in client.iter_dialogs(limit=50):
                if "NATIJA" in d.name.upper():
                    print(f"Potential Match: {d.name}")

        await client.disconnect()
    except Exception as e:
        print(f"Global Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
