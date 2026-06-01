from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers.messages import process_message_logic


@pytest.mark.asyncio
async def test_business_reply_uses_bot_send_message_with_connection_id(monkeypatch):
    bot = MagicMock()
    bot.send_message = AsyncMock()
    message = SimpleNamespace(
        text="Narxlarni yuboring",
        caption=None,
        photo=None,
        voice=None,
        reply_to_message=None,
        message_id=91,
        get_bot=lambda: bot,
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=7,
            username="client",
            first_name="Client",
            is_bot=False,
        ),
        effective_chat=SimpleNamespace(id=8, type="private", title=None),
        message=None,
        business_message=message,
    )
    action_parser = MagicMock()
    action_parser.parse_and_execute = AsyncMock(return_value="Javob")
    controller = MagicMock()
    controller.get_response = AsyncMock(return_value="AI javob")
    monkeypatch.setattr("src.handlers.messages.config.TELEGRAM_AI_STREAMING_ENABLED", False, raising=False)

    await process_message_logic(
        update,
        None,
        MagicMock(),
        action_parser,
        controller,
        is_business=True,
        msg_business_connection_id="biz-1",
    )

    bot.send_message.assert_awaited_once_with(
        chat_id=8,
        text="Javob",
        parse_mode="HTML",
        business_connection_id="biz-1",
        reply_to_message_id=91,
    )
