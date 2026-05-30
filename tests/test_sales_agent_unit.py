import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.sales_agent import SalesAgent

@pytest.mark.asyncio
async def test_sales_agent_init():
    api_keys = {"GEMINI_API_KEY": "test_key"}
    agent = SalesAgent("test_agent", "System Prompt", api_keys)
    assert agent.agent_id == "test_agent"
    assert agent.system_prompt == "System Prompt"
    assert isinstance(agent.products, dict)

@pytest.mark.asyncio
async def test_detect_escalation_triggers():
    agent = SalesAgent("test", "test", {"GEMINI": "test"})
    
    # Test trigger word
    reason = agent._detect_escalation("Meni aldadi bu kompaniya!", None)
    assert reason == "trigger_word:aldadi"
    
    # Test low probability
    assessment = MagicMock()
    assessment.close_probability = 0.1
    assessment.risk_flags = []
    reason = agent._detect_escalation("Normal message", assessment)
    assert reason == "low_close_prob:0.10"
    
    # Test risk flag
    assessment.close_probability = 0.8
    assessment.risk_flags = ["legal_review"]
    reason = agent._detect_escalation("Normal message", assessment)
    assert reason == "risk_flag:legal_review"

@pytest.mark.asyncio
async def test_extract_meeting_window():
    agent = SalesAgent("test", "test", {"GEMINI": "test"})
    
    # Valid meeting string
    text = "Ertaga soat 14:00 da uchrashuv qilaylik"
    window = agent._extract_meeting_window(text)
    assert window is not None
    assert "start_time" in window
    assert "end_time" in window
    
    # Invalid
    assert agent._extract_meeting_window("Salom") is None

@pytest.mark.asyncio
async def test_process_task_flow():
    db = AsyncMock()
    executor = AsyncMock()
    api_keys = {"GEMINI_API_KEY": "test_key"}
    
    executor.execute.return_value = {"success": True, "details": "Action executed"}
    agent = SalesAgent("test_agent", "System Prompt", api_keys, executor=executor, db=db)
    
    # Mock semantic assessment path
    assessment = MagicMock()
    assessment.to_payload.return_value = {"stage": "discovery"}
    assessment.approval_needed = False
    assessment.autonomy_mode = "autonomous"
    assessment.recommended_status = "Interested"
    assessment.intent = "discovery"
    assessment.objection = None
    assessment.urgency = "low"
    assessment.sentiment = "positive"
    assessment.close_probability = 0.5
    assessment.next_action = "continue"
    assessment.risk_flags = []
    
    with patch("src.agents.sales_agent.NegotiationEngine.assess_async", new_callable=AsyncMock) as mock_assess, \
         patch("src.agents.sales_agent.SalesAgent.call_ai_with_fallback", new_callable=AsyncMock) as mock_ai, \
         patch("src.agents.sales_agent.SalesAgent.load_session_history", new_callable=AsyncMock), \
         patch("src.agents.sales_agent.SalesAgent.get_session_history", return_value=[]):
        
        mock_assess.return_value = assessment
        mock_ai.return_value = "Assalomu alaykum! Qanday yordam bera olaman?"
        
        reply = await agent.process_task(12345, "Salom, menga logo kerak")
        
        assert reply == "Assalomu alaykum! Qanday yordam bera olaman?"
        assert db.log_agent_action.called
        # Check if status update was planned
        executor.execute.assert_any_call("update_lead_status", {"user_id": 12345, "status_name": "Interested"}, context_user_id=12345)
