import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live Gemini summary test; set RUN_LIVE_TESTS=1 to run intentionally.",
)


async def test_ai_summary_live():
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY is required for live Gemini summary test"

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Bu sinov xabari. Iltimos, ushbu xabarni 1 ta so'z bilan xulosalang: 'Salom, ishlar yaxshimi?'",
        config=types.GenerateContentConfig(system_instruction="Siz aqlli yordamchisiz."),
    )

    assert response.text
