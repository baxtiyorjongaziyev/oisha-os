from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

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


@pytest.mark.asyncio
async def test_kirim_topic_income_event_sends_celebration_once(monkeypatch):
    db = MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock()
    message = SimpleNamespace(
        message="Logo loyiha uchun avans 1 500 000 so'm tushdi",
        reply_to_msg_id=168,
        reply_to=None,
        reply_to_top_id=None,
    )
    event = MagicMock(chat_id=-100123, id=88, message=message)
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=False, username="seller", first_name="Seller")
    )

    monkeypatch.setattr(main, "bot_client", bot_client)
    monkeypatch.setattr(main, "advisor_agent", None)
    monkeypatch.setattr(main, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(main.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(main.settings, "TOPIC_KIRIM_ID", 168, raising=False)

    await main.kirim_topic_handler(event)

    bot_client.send_message.assert_awaited_once()
    assert db.set_state.await_args_list == [
        call("kirim_celebration:-100123:88", "started"),
        call("kirim_celebration:-100123:88", "done"),
    ]
