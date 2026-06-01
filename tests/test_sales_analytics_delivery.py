from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.sales_analytics import SalesAnalytics
from src.services.core.tool_adapters import configure_userbot_group_fallback


@pytest.fixture(autouse=True)
def reset_userbot_fallback():
    configure_userbot_group_fallback(None)
    yield
    configure_userbot_group_fallback(None)


@pytest.mark.asyncio
async def test_report_uses_running_userbot_when_bot_lacks_group_access():
    analytics = SalesAnalytics.__new__(SalesAnalytics)
    analytics.bot = MagicMock()
    analytics.bot.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    userbot = MagicMock()
    userbot.send_message = AsyncMock()
    configure_userbot_group_fallback(userbot)

    await analytics._send_report(-100123, "<b>Hisobot</b>", thread_id=52)

    userbot.send_message.assert_awaited_once_with(
        -100123,
        "<b>Hisobot</b>",
        reply_to=52,
        parse_mode="html",
        link_preview=True,
    )
