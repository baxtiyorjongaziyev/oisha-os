import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live Gemini contact extraction test; set RUN_LIVE_TESTS=1 to run intentionally.",
)


def test_ai_response_live(tmp_path):
    from google import genai
    from google.genai import types
    from src.services.core.persona_hub import get_persona

    gemini_key = os.getenv("GEMINI_API_KEY")
    assert gemini_key, "GEMINI_API_KEY is required for live Gemini contact test"

    client = genai.Client(api_key=gemini_key)
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(system_instruction=get_persona(is_team_member=True)),
    )
    response = chat.send_message(
        "Salom, mening ismim Olim. Men Toshkentdanman, qurilish sohasida tadbirkorman. Raqamim: +998901112233"
    )

    (tmp_path / "ai_response_last.txt").write_text(response.text or "", encoding="utf-8")
    assert response.text
