import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.schedulers.cloud_brain_synthesizer import (
    _fetch_recent_data,
    _generate_insights,
    run_brain_synthesizer_cycle,
)
from src.services.utils.free_ai_router import ProviderResult

@pytest.mark.asyncio
async def test_generate_insights_empty():
    assert await _generate_insights("") is None
    assert await _generate_insights(None) is None

@pytest.mark.asyncio
async def test_generate_insights_success():
    fake_result = ProviderResult(
        text="### 1. 🔄 Context Switching\n- Task A done\n### 2. 💡 Content Machine\n- Idea 1",
        provider="groq",
        model="compound"
    )
    with patch("src.schedulers.cloud_brain_synthesizer.FreeAIProviderRouter") as mock_router_cls:
        mock_router = MagicMock()
        mock_router.generate_text = AsyncMock(return_value=fake_result)
        mock_router_cls.return_value = mock_router

        result = await _generate_insights("Task: 1 - Design logo")
        assert result is not None
        assert "Context Switching" in result

@pytest.mark.asyncio
async def test_generate_insights_failure_fails_closed():
    with patch("src.schedulers.cloud_brain_synthesizer.FreeAIProviderRouter") as mock_router_cls:
        mock_router = MagicMock()
        mock_router.generate_text = AsyncMock(side_effect=RuntimeError("All providers failed"))
        mock_router_cls.return_value = mock_router

        result = await _generate_insights("Task: 1 - Design logo")
        # Fail-closed: returns None instead of an error message
        assert result is None

@pytest.mark.asyncio
async def test_run_cycle_skips_when_no_data():
    bot = AsyncMock()
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="")):
        await run_brain_synthesizer_cycle(bot, 12345)
        bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_run_cycle_skips_when_no_insights():
    bot = AsyncMock()
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: 1 - Design")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=None)):
            await run_brain_synthesizer_cycle(bot, 12345)
            bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_run_cycle_skips_when_mostly_no_data():
    bot = AsyncMock()
    sparse_text = "### 1. Ma'lumot yo'q.\n### 2. Ma'lumot yo'q.\n### 3. Ma'lumot yo'q.\n### 4. Ma'lumot yo'q."
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: 1 - Design")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=sparse_text)):
            await run_brain_synthesizer_cycle(bot, 12345)
            bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_run_cycle_sends_on_valid_insights():
    bot = AsyncMock()
    valid_text = "### 1. 🔄 Context Switching\n- Next step\n### 2. 💡 Content Machine\n- Idea"
    with patch("src.schedulers.cloud_brain_synthesizer._fetch_recent_data", AsyncMock(return_value="Task: 1 - Design")):
        with patch("src.schedulers.cloud_brain_synthesizer._generate_insights", AsyncMock(return_value=valid_text)):
            with patch("src.schedulers.cloud_brain_synthesizer.push_vault_to_remote", AsyncMock()):
                await run_brain_synthesizer_cycle(bot, 12345)
                bot.send_message.assert_called_once()
                args, kwargs = bot.send_message.call_args
                assert args[0] == 12345
                assert "Second Brain Evolution Digest" in args[1]
                assert "Context Switching" in args[1]
