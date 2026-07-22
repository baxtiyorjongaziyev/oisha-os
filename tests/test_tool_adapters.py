from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.tool_adapters import (
    TelegramNotificationAdapter,
    configure_userbot_group_fallback,
    send_group_message_with_fallback,
)


@pytest.fixture(autouse=True)
def reset_userbot_fallback():
    configure_userbot_group_fallback(None)
    yield
    configure_userbot_group_fallback(None)


@pytest.mark.asyncio
async def test_group_send_uses_running_userbot_when_bot_lacks_group_access():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    userbot = MagicMock()
    userbot.send_message = AsyncMock(return_value=SimpleNamespace(id=88))
    configure_userbot_group_fallback(userbot)

    message = await send_group_message_with_fallback(
        bot,
        chat_id=-100123,
        text="Hisobot",
        thread_id=52,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    assert message.id == 88
    userbot.send_message.assert_awaited_once_with(
        -100123,
        "Hisobot",
        reply_to=52,
        parse_mode="html",
        link_preview=False,
    )


@pytest.mark.asyncio
async def test_notification_adapter_reports_userbot_fallback_message_id():
    adapter = TelegramNotificationAdapter("123456:fake-token")
    adapter.bot = MagicMock()
    adapter.bot.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    userbot = MagicMock()
    userbot.send_message = AsyncMock(return_value=SimpleNamespace(id=99))
    configure_userbot_group_fallback(userbot)

    result = await adapter.send_group_message(-100123, "Hisobot", thread_id=52)

    assert result.success is True
    assert result.group_message_id == 99
