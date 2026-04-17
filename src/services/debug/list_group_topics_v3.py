import asyncio
from telethon import TelegramClient, functions, types
from settings import settings

async def main():
    try:
        client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
        await client.connect()
        print("Connected.")
        
        # Get the group entity first to ensure we have the correct peer
        group_id = -1003820339529
        entity = await client.get_input_entity(group_id)
        print(f"Peer found for {group_id}")
        
        # Correctly call GetForumTopicsRequest
        try:
            result = await client(functions.channels.GetForumTopicsRequest(
                channel=entity,
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))
            for topic in result.topics:
                # topic is usually a ForumTopic
                if hasattr(topic, 'title'):
                    print(f"TOPIC FOUND: '{topic.title}' | ID: {topic.id}")
                else:
                    # In some versions/responses it might be ForumTopicDeleted or similar
                    print(f"Untyped Topic Found: ID {topic.id}")
        except Exception as e:
            print(f"Error calling GetForumTopicsRequest: {e}")

        await client.disconnect()
    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
