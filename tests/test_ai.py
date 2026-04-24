import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live Gemini smoke test; set RUN_LIVE_TESTS=1 to run intentionally.",
)


def test_gemini_generate_content_live():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY is required for live Gemini smoke test"

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Salom, sen kimsan?",
    )

    assert response.text
