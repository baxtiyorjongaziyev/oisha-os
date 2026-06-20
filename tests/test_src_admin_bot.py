"""
Unit tests for AdminBot in src/admin_bot.py.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.admin_bot import AdminBot


@pytest.mark.asyncio
async def test_send_recent_leads_no_leads():
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_db.get_recent_active_leads = AsyncMock(return_value=[])
    mock_msg_controller = MagicMock()
    
    bot = AdminBot(mock_client, mock_db, mock_msg_controller)
    mock_event = AsyncMock()
    
    # Act
    await bot.send_recent_leads(mock_event)
    
    # Assert
    mock_event.respond.assert_called_once()
    args, _ = mock_event.respond.call_args
    assert "Hozircha ma'lumotlar bazasida yaqin oradagi faol lidlar" in args[0]


@pytest.mark.asyncio
async def test_send_recent_leads_with_leads():
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    
    lead_data = [
        {
            "first_name": "Alisher",
            "username": "alisher_dev",
            "phone": "+998991234567",
            "intent": "Branding",
            "journey_stage": "Negotiation",
            "journey_next_action": "Call tomorrow",
            "amo_lead_id": 12345,
            "last_client_message": "Salom, narxlarni tashlab bering"
        }
    ]
    mock_db.get_recent_active_leads = AsyncMock(return_value=lead_data)
    mock_msg_controller = MagicMock()
    
    bot = AdminBot(mock_client, mock_db, mock_msg_controller)
    mock_event = AsyncMock()
    
    # Act
    await bot.send_recent_leads(mock_event)
    
    # Assert
    mock_event.respond.assert_called_once()
    args, _ = mock_event.respond.call_args
    assert "Alisher" in args[0]
    assert "alisher_dev" in args[0]
    assert "+998991234567" in args[0]
    assert "Branding" in args[0]
    assert "Negotiation" in args[0]
    assert "Call tomorrow" in args[0]
    assert "https://jonbrandingagency.amocrm.ru/leads/detail/12345" in args[0]
    assert "Salom, narxlarni tashlab bering" in args[0]
