from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers.messages import is_leaked_response, process_message_logic


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


def test_is_leaked_response_detects_system_and_harness_errors():
    assert is_leaked_response("[The tool failed to complete the task. Review the latest error message...]")
    assert is_leaked_response("[NO TOOL CALL — a standalone response]")
    assert is_leaked_response("[Tool loop warning: same_tool_failure_warning; count=2...]")
    assert is_leaked_response("Reply \"skip\" to skip this question.")
    assert is_leaked_response("Do not guess, and never invent fake data or results.")
    assert is_leaked_response("skill_manage has failed 2 times this turn")
    assert not is_leaked_response("Assalomu alaykum! Sizga qanday yordam bera olaman?")


@pytest.mark.asyncio
async def test_group_message_not_addressed_stays_silent(monkeypatch):
    message = SimpleNamespace(
        text="📊 Kunlik moliya — 27.10.2026 Kirim: 0 Chiqim: 4 910 000",
        caption=None,
        photo=None,
        voice=None,
        reply_to_message=None,
        message_id=102,
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=11, username="dilbar", first_name="Dilbar", is_bot=False),
        effective_chat=SimpleNamespace(id=-1001234567, type="supergroup", title="Team"),
        message=message,
        business_message=None,
    )
    controller = MagicMock()
    controller.get_response = AsyncMock(return_value="AI response")
    action_parser = MagicMock()

    await process_message_logic(update, None, MagicMock(), action_parser, controller)

    controller.get_response.assert_not_called()
    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_group_message_addressed_responds(monkeypatch):
    message = SimpleNamespace(
        text="@jonairobot Salom, bugungi reja qanday?",
        caption=None,
        photo=None,
        voice=None,
        reply_to_message=None,
        message_id=103,
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=11, username="dilbar", first_name="Dilbar", is_bot=False),
        effective_chat=SimpleNamespace(id=-1001234567, type="supergroup", title="Team"),
        message=message,
        business_message=None,
    )
    controller = MagicMock()
    controller.get_response = AsyncMock(return_value="Bugun 3 ta asosiy vazifa bor.")
    action_parser = MagicMock()
    action_parser.parse_and_execute = AsyncMock(return_value="Bugun 3 ta asosiy vazifa bor.")

    await process_message_logic(update, None, MagicMock(), action_parser, controller)

    controller.get_response.assert_called_once()
    message.reply_text.assert_called_once_with("Bugun 3 ta asosiy vazifa bor.", parse_mode="HTML")


@pytest.mark.asyncio
async def test_group_message_leaked_response_dropped_silently(monkeypatch):
    message = SimpleNamespace(
        text="@jonairobot Kunlik balansni hisobla",
        caption=None,
        photo=None,
        voice=None,
        reply_to_message=None,
        message_id=104,
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=11, username="dilbar", first_name="Dilbar", is_bot=False),
        effective_chat=SimpleNamespace(id=-1001234567, type="supergroup", title="Team"),
        message=message,
        business_message=None,
    )
    controller = MagicMock()
    controller.get_response = AsyncMock(return_value="[The tool failed to complete the task.]")
    action_parser = MagicMock()
    action_parser.parse_and_execute = AsyncMock(return_value="[The tool failed to complete the task.]")

    await process_message_logic(update, None, MagicMock(), action_parser, controller)

    # In group chat, leaked response is dropped silently (no reply sent)
    message.reply_text.assert_not_called()
