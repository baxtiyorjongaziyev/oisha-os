import asyncio
import os
from src.schedulers.frog_scheduler import send_daily_frog_brief

class MockClient:
    async def send_message(self, chat_id, text, parse_mode=None):
        print(f"Message to {chat_id}:\\n{text}")

async def test_frog():
    client = MockClient()
    await send_daily_frog_brief(bot_client=client, team_group_id=123)

if __name__ == "__main__":
    asyncio.run(test_frog())
