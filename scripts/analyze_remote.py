import asyncio
import base64
import urllib.request
import urllib.error

import anyio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    url = "https://oisha.jonbranding.uz/telegram-mcp/messages"
    auth = base64.b64encode(b"oisha:oisha_safe_123").decode()
    headers = {"Authorization": f"Basic {auth}"}
    
    try:
        async with sse_client(url, headers=headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                res = await session.call_tool("get_recent_dialogs", arguments={"limit": 10})
                print("Dialogs:")
                print(res.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    anyio.run(main)
