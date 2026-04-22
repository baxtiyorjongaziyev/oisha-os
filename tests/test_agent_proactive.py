import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live proactive agent test calls LLM/business services; set RUN_LIVE_TESTS=1 to run intentionally.",
)


async def test_proactive_behavior_live():
    from src.database import Database
    from src.controllers.message_controller import MessageController

    gemini_key = os.getenv("GEMINI_API_KEY")
    assert gemini_key, "GEMINI_API_KEY is required for live proactive agent test"

    db = Database()
    await db.init_db()
    controller = MessageController({"gemini": gemini_key}, db=db)

    class MockBotApp:
        class MockBot:
            async def send_message(self, chat_id, text, **kwargs):
                return None

        bot = MockBot()

    controller.set_bot_app(MockBotApp())
    response = await controller.get_response(
        999999,
        "Test Client",
        "Salom! Menga yangi fast-food brendi uchun logotip va nom kerak. Telefonim: +998901234567",
    )

    assert response
