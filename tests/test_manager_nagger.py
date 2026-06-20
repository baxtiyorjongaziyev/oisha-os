import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.manager_nagger import ManagerNagger
import src.config as config


@pytest.mark.asyncio
async def test_nag_about_stagnation_sends_telegram():
    # Arrange
    mock_amo = MagicMock()
    mock_db = AsyncMock()
    mock_bot = AsyncMock()
    mock_ai = MagicMock()

    nagger = ManagerNagger(amo=mock_amo, db=mock_db, bot=mock_bot, ai_client=mock_ai)

    stagnant_leads = [
        {"id": 1, "name": "Lead A", "price": 1000},
        {"id": 2, "name": "Lead B", "price": 2000},
    ]

    # Act
    with patch("src.services.core.manager_nagger.safe_ai_call", return_value="Kinoyali xabar") as mock_safe_call:
        message = await nagger.nag_about_stagnation(
            manager_id=12345, manager_name="Diyor", stagnant_leads=stagnant_leads
        )

        # Assert
        assert message == "Kinoyali xabar"
        mock_bot.send_message.assert_called_once_with(12345, "Kinoyali xabar", parse_mode="html")
        mock_db.log_agent_action.assert_called_once()
        mock_safe_call.assert_called_once()


@pytest.mark.asyncio
async def test_generate_public_shame_report_success():
    # Arrange
    mock_amo = MagicMock()
    mock_db = AsyncMock()
    mock_bot = AsyncMock()
    mock_ai = MagicMock()

    nagger = ManagerNagger(amo=mock_amo, db=mock_db, bot=mock_bot, ai_client=mock_ai)

    mock_amo.check_stagnated_leads = MagicMock(return_value=[
        {"id": 1, "name": "Lead X", "responsible_user_id": 99},
        {"id": 2, "name": "Lead Y", "responsible_user_id": 99},
    ])
    mock_amo.get_user_name = MagicMock(return_value="Diyor")

    # Set config value directly
    config.CRM_GROUP_ID = -100123456

    # Act
    with patch("src.services.core.manager_nagger.safe_ai_call", return_value="Shame report message") as mock_safe_call:
        message = await nagger.generate_public_shame_report()

        # Assert
        assert message == "Shame report message"
        mock_bot.send_message.assert_called_once_with(-100123456, "Shame report message", parse_mode="html")
        mock_db.log_agent_action.assert_called_once()
        mock_safe_call.assert_called_once()
