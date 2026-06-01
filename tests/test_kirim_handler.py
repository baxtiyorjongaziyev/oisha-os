from unittest.mock import AsyncMock, MagicMock

import pytest

from src import main


@pytest.mark.asyncio
async def test_kirim_send_falls_back_to_userbot_reply(monkeypatch):
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    event = MagicMock(id=77)
    event.reply = AsyncMock()

    monkeypatch.setattr(main, "bot_client", bot_client)
    monkeypatch.setattr(main.settings, "TEAM_GROUP_ID", -100123, raising=False)

    await main._send_kirim_celebration(event, "Tabriklaymiz!")

    bot_client.send_message.assert_awaited_once()
    event.reply.assert_awaited_once_with("Tabriklaymiz!", link_preview=False)
