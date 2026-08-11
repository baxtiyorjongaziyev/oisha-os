from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.routes import telegram_mcp


@pytest.mark.asyncio
async def test_api_history_uses_before_id_as_telegram_max_id():
    client = SimpleNamespace(get_messages=AsyncMock(return_value=[]))
    with patch.object(telegram_mcp.app_ctx, "client", client):
        result = await telegram_mcp.get_chat_history(
            "-100123", limit=25, before_id=3873
        )

    assert result == {"messages": []}
    client.get_messages.assert_awaited_once_with(
        -100123,
        limit=25,
        max_id=3873,
    )
