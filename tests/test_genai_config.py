import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live Gemini chat config test; set RUN_LIVE_TESTS=1 to run intentionally.",
)


def test_gemini_chat_config_live():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY is required for live Gemini config test"

    client = genai.Client(api_key=api_key)
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config={"system_instruction": "You are a helpful assistant."},
    )
    response = chat.send_message("Hello, who are you?")

    assert response.text
