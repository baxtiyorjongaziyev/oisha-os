import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live Telegram reach test sends real messages; set RUN_LIVE_TESTS=1 to run intentionally.",
)


async def test_bot_reach_live():
    from telegram import Bot

    token = os.getenv("BOT_TOKEN")
    assert token, "BOT_TOKEN is required for live Telegram reach test"

    owner_id = int(os.getenv("LIVE_TEST_OWNER_ID", "5824905101"))
    bot = Bot(token=token)
    chat = await bot.get_chat(owner_id)
    assert chat.id == owner_id
