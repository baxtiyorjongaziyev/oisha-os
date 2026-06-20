"""
Unit tests for SLAMonitor in src/services/core/sla_monitor.py.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta
from src.services.core.sla_monitor import SLAMonitor


@pytest.mark.asyncio
async def test_sla_monitor_no_unanswered_chats():
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_advisor = MagicMock()
    mock_admin_bot = MagicMock()
    
    async def mock_iter_dialogs(limit=30):
        if False:
            yield None
            
    mock_client.iter_dialogs = mock_iter_dialogs
    
    monitor = SLAMonitor(
        client=mock_client,
        db=mock_db,
        advisor=mock_advisor,
        admin_bot=mock_admin_bot,
        sla_limit_minutes=10
    )
    
    # Act
    await monitor.check_all_active_chats()
    
    # Assert
    assert len(monitor.escalated_chats) == 0


@pytest.mark.asyncio
async def test_sla_monitor_escalates_unanswered_chat():
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_advisor = MagicMock()
    mock_admin_bot = MagicMock()
    
    mock_db.is_crm_synced = AsyncMock(return_value=True)
    
    # Mock last message: from client (out=False), wait time > 10m
    mock_message = MagicMock()
    mock_message.out = False
    mock_message.text = "Hello, pricing please?"
    mock_message.date = datetime.now() - timedelta(minutes=15)
    
    mock_dialog = MagicMock()
    mock_dialog.id = 999
    mock_dialog.is_user = True
    mock_dialog.entity.bot = False
    mock_dialog.entity.first_name = "Botir"
    mock_dialog.message = mock_message
    
    async def mock_iter_dialogs(limit=30):
        yield mock_dialog
        
    mock_client.iter_dialogs = mock_iter_dialogs
    
    async def mock_iter_messages(chat_id, limit=5):
        msg = MagicMock()
        msg.out = False
        msg.text = "Hello, pricing please?"
        yield msg
        
    mock_client.iter_messages = mock_iter_messages
    
    mock_advisor.analyze_and_advise = AsyncMock(return_value="Suggested draft response")
    mock_admin_bot.notify_lead = AsyncMock()
    
    monitor = SLAMonitor(
        client=mock_client,
        db=mock_db,
        advisor=mock_advisor,
        admin_bot=mock_admin_bot,
        sla_limit_minutes=10
    )
    
    # Act
    await monitor.check_all_active_chats()
    
    # Assert
    assert 999 in monitor.escalated_chats
    mock_admin_bot.notify_lead.assert_called_once()
    args, _ = mock_admin_bot.notify_lead.call_args
    assert "SLA BUZILDI" in args[0]
    assert "Botir" in args[0]
    assert "Suggested draft response" in args[0]
