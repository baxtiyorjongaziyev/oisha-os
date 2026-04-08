import asyncio
from telethon import TelegramClient, functions
from settings import settings

async def main():
    try:
        client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
        await client.connect()
        print("Connected.")
        
        # Search for any forum related functions in the library
        import telethon.tl.functions as funcs
        modules = [funcs.channels, funcs.messages, funcs]
        
        print("Searching for 'Forum' or 'Topic' attributes...")
        for mod in modules:
            attrs = [a for a in dir(mod) if 'Forum' in a or 'Topic' in a]
            if attrs:
                print(f"Module {mod.__name__} has: {attrs}")
                
        await client.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
