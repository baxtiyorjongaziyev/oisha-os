from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.admin_bot import AdminBot


@pytest.mark.asyncio
async def test_notify_team_uses_userbot_fallback_when_bot_lacks_group_access():
    admin_bot = AdminBot.__new__(AdminBot)
    admin_bot.team_group_id = -100123
    admin_bot.bot_client = MagicMock()
    admin_bot.bot_client.send_message = AsyncMock(
        side_effect=RuntimeError("chat not found")
    )
    admin_bot.user_client = MagicMock()
    admin_bot.user_client.send_message = AsyncMock()

    await admin_bot.notify_team(
        "Muhim bildirishnoma",
        buttons=[["bot-only button"]],
        topic_id=52,
        parse_mode="HTML",
    )

    admin_bot.user_client.send_message.assert_awaited_once_with(
        -100123,
        "Muhim bildirishnoma",
        reply_to=52,
        parse_mode="HTML",
    )


@pytest.mark.asyncio
async def test_notify_team_prefers_bot_delivery_when_available():
    admin_bot = AdminBot.__new__(AdminBot)
    admin_bot.team_group_id = -100123
    admin_bot.bot_client = MagicMock()
    admin_bot.bot_client.send_message = AsyncMock()
    admin_bot.user_client = MagicMock()
    admin_bot.user_client.send_message = AsyncMock()

    await admin_bot.notify_team("Hisobot", topic_id=52)

    admin_bot.bot_client.send_message.assert_awaited_once_with(
        -100123,
        "Hisobot",
        buttons=None,
        reply_to=52,
        parse_mode=None,
    )
    admin_bot.user_client.send_message.assert_not_awaited()
