import asyncio
from telethon import TelegramClient
from settings import settings

async def main():
    try:
        client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
        await client.connect()
        
        group_id = -1003820339529
        topic_id = 7
        
        print(f"\n--- TOPIC ID {topic_id} MASHG'ULOTLARI ---")
        async for message in client.iter_messages(group_id, reply_to=topic_id, limit=5):
            author = "Unknown"
            if message.sender:
                author = getattr(message.sender, 'first_name', 'NoName')
            
            print(f"ID: {message.id} | Kim: {author}")
            print(f"MATN: {message.text[:150]}...")
            print("-" * 20)
            
        await client.disconnect()
    except Exception as e:
        print(f"Inspection Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
