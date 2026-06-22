from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.handlers import kirim


@pytest.mark.asyncio
async def test_kirim_send_falls_back_to_userbot_reply(monkeypatch):
    from src.context import app_ctx
    bot_client_mock = MagicMock()
    bot_client_mock.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    event = MagicMock(id=77)
    event.reply = AsyncMock()

    monkeypatch.setattr(app_ctx, "bot_client", bot_client_mock)
    monkeypatch.setattr(kirim.settings, "TEAM_GROUP_ID", -100123, raising=False)

    await kirim._send_kirim_celebration(event, "Tabriklaymiz!")

    bot_client_mock.send_message.assert_awaited_once()
    event.reply.assert_awaited_once_with("Tabriklaymiz!", link_preview=False)


@pytest.mark.asyncio
async def test_kirim_topic_income_event_sends_celebration_once(monkeypatch):
    from src.context import app_ctx
    db = MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    bot_client_mock = MagicMock()
    bot_client_mock.send_message = AsyncMock()
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

    monkeypatch.setattr(app_ctx, "bot_client", bot_client_mock)
    monkeypatch.setattr(app_ctx, "advisor_agent", None)
    monkeypatch.setattr(app_ctx, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(kirim.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(kirim.settings, "TOPIC_KIRIM_ID", 168, raising=False)

    await kirim.kirim_topic_handler(event)

    bot_client_mock.send_message.assert_awaited_once()
    assert db.set_state.await_args_list == [
        call("kirim_celebration:-100123:88", "started"),
        call("kirim_celebration:-100123:88", "done"),
    ]
