import json
import pytest
from unittest.mock import AsyncMock, patch

from src.services.core.llm_coach import SalesCoachLLM

class DummyResult:
    def __init__(self, text: str):
        self.text = text

@pytest.mark.asyncio
async def test_generate_tip_successful():
    mock_router = AsyncMock()
    mock_router.generate_content = AsyncMock(return_value=DummyResult(
        json.dumps({"tip": "Offer a discount", "category": "upsell"})
    ))
    with patch("src.services.core.llm_coach.get_free_ai_router", return_value=mock_router):
        tip = await SalesCoachLLM.generate_tip(
            transcript="Mijoz narx so'radi", segments=None, context={"crm_status": "new"}
        )
    assert tip == {"tip": "Offer a discount", "category": "upsell"}
    mock_router.generate_content.assert_awaited_once()

@pytest.mark.asyncio
async def test_generate_tip_invalid_json_returns_none():
    mock_router = AsyncMock()
    mock_router.generate_content = AsyncMock(return_value=DummyResult("not a json"))
    with patch("src.services.core.llm_coach.get_free_ai_router", return_value=mock_router):
        tip = await SalesCoachLLM.generate_tip(
            transcript="test", segments=None, context=None
        )
    assert tip is None

@pytest.mark.asyncio
async def test_generate_tip_truncates_long_tip():
    long_tip = "x" * 300
    mock_router = AsyncMock()
    mock_router.generate_content = AsyncMock(return_value=DummyResult(
        json.dumps({"tip": long_tip, "category": "other"})
    ))
    with patch("src.services.core.llm_coach.get_free_ai_router", return_value=mock_router):
        tip = await SalesCoachLLM.generate_tip(
            transcript="test", segments=None, context=None
        )
    assert len(tip["tip"]) == 200
    assert tip["category"] == "other"
