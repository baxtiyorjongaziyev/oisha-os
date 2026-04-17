import asyncio
from telethon import TelegramClient, functions, types
from settings import settings

async def main():
    try:
        client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
        await client.connect()
        print("Connected.")
        
        group_id = -1003820339529
        peer = await client.get_input_entity(group_id)
        print(f"Peer found for {group_id}")
        
        # Correctly call messages.GetForumTopicsRequest
        result = await client(functions.messages.GetForumTopicsRequest(
            peer=peer,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=100
        ))
        
        print("\n--- GURUH MAVZULARI (TOPICS) ---")
        for topic in result.topics:
            if hasattr(topic, 'title'):
                print(f"TOPIC: '{topic.title}' | ID: {topic.id}")
            else:
                print(f"Untyped Topic: ID {topic.id}")
        print("--------------------------------\n")
        
        await client.disconnect()
    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
