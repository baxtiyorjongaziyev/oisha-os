import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.daily_enforcer import DailyEnforcer
import src.config as config


@pytest.mark.asyncio
async def test_daily_enforcer_notification():
    # Arrange
    mock_bot = AsyncMock()
    enforcer = DailyEnforcer(bot=mock_bot)

    # Act
    await enforcer._send_notification(user_id="123", message="Morning standing plan", priority="high")

    # Assert
    mock_bot.send_message.assert_called_once_with("123", "Morning standing plan", parse_mode="html")


@pytest.mark.asyncio
async def test_daily_enforcer_send_to_director():
    # Arrange
    mock_bot = AsyncMock()
    enforcer = DailyEnforcer(bot=mock_bot)

    # Set config value directly
    config.OWNER_ID = "999"

    # Act
    await enforcer._send_to_director(message="Director summary report")

    # Assert
    mock_bot.send_message.assert_called_once_with("999", "Director summary report", parse_mode="html")
