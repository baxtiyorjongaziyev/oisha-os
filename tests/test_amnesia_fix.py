import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live memory test calls Gemini; set RUN_LIVE_TESTS=1 to run intentionally.",
)


async def test_memory_live():
    from google import genai
    from src.database import Database
    import src.userbot as userbot

    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY is required for live memory test"

    db = Database("bot_database.db")
    await db.init_db()
    test_user_id = 999111222
    await db.upsert_user(
        test_user_id,
        "Test User",
        phone="+998901234567",
        service_type="Logotip vizitka",
        deadline="1 hafta",
    )

    userbot.ai_client = genai.Client(api_key=api_key)
    userbot.db = db
    response = await userbot.get_reply(test_user_id, "Test User", message_text="Meni ismim va raqamim nima edi?")

    assert response
