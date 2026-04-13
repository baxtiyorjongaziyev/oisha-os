import asyncio
from telethon import TelegramClient, functions
from settings import settings

async def main():
    try:
        client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
        await client.connect()
        print("Connected.")
        
        group_id = -1003820339529
        print(f"Fetching topics for group {group_id}...")
        
        # Correct function for forum topics in recent Telethon versions
        try:
            result = await client(functions.channels.GetForumTopicsRequest(
                channel=group_id,
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))
            for topic in result.topics:
                print(f"TOPIC FOUND: '{topic.title}' | ID: {topic.id}")
        except Exception as e:
            print(f"Sub-error: {e}. Trying alternative attribute...")
            # Some versions use functions.messages.GetForumTopicsRequest
            result = await client(functions.messages.GetForumTopicsRequest(
                channel=group_id,
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))
            for topic in result.topics:
                print(f"TOPIC FOUND: '{topic.title}' | ID: {topic.id}")

        await client.disconnect()
    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
