from unittest.mock import patch

import pytest

from src.agents.negotiation_engine import NegotiationEngine


@pytest.mark.asyncio
async def test_assess_async_falls_back_when_context_is_none():
    with patch(
        "src.agents.negotiation_engine.genai.Client",
        side_effect=RuntimeError("gemini unavailable"),
    ):
        assessment = await NegotiationEngine.assess_async(
            "Narx qancha bo'ladi?", context=None
        )

    assert assessment.intent == "pricing"
    assert assessment.autonomy_mode == "autonomous"
