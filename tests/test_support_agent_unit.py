import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.support_agent import SupportAgent

@pytest.mark.asyncio
async def test_support_agent_init():
    agent = SupportAgent("support_agent", "System Prompt", {"KEY": "VAL"})
    assert agent.agent_id == "support_agent"

@pytest.mark.asyncio
async def test_support_agent_process_task():
    api_keys = {"GEMINI_API_KEY": "test_key"}
    agent = SupportAgent("support", "Prompt", api_keys)
    
    with patch("src.agents.support_agent.SupportAgent.call_ai_with_fallback", new_callable=AsyncMock) as mock_ai, \
         patch("src.agents.support_agent.SupportAgent.load_session_history", new_callable=AsyncMock), \
         patch("src.agents.support_agent.SupportAgent.get_session_history", return_value=[]), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()) as mock_open:
        
        mock_open.return_value.__enter__.return_value.read.return_value = "Mock KB content"
        mock_ai.return_value = "Yordam bera olaman."
        
        reply = await agent.process_task(12345, "Qanday xizmatlar bor?")
        
        assert reply == "Yordam bera olaman."
        assert mock_ai.called
