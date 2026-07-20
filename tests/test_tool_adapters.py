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


@pytest.mark.asyncio
async def test_send_group_poll_forwards_bot_api_10_limits():
    adapter = TelegramNotificationAdapter("123456:fake-token")
    adapter.bot_api10 = MagicMock()
    adapter.bot_api10.send_poll = AsyncMock(return_value={"message_id": 4242})

    result = await adapter.send_group_poll(
        -100123,
        "Ish rejasi tayyormi?",
        [{"text": "Ha"}, {"text": "Yo'q"}],
        members_only=True,
        country_codes=["UZ"],
        thread_id=7,
    )

    assert result.success is True
    assert result.group_message_id == 4242
    adapter.bot_api10.send_poll.assert_awaited_once()
    kwargs = adapter.bot_api10.send_poll.await_args.kwargs
    assert kwargs["members_only"] is True
    assert kwargs["country_codes"] == ["UZ"]
    assert kwargs["message_thread_id"] == 7


@pytest.mark.asyncio
async def test_clear_message_reactions_targets_single_user_or_all():
    adapter = TelegramNotificationAdapter("123456:fake-token")
    adapter.bot_api10 = MagicMock()
    adapter.bot_api10.delete_message_reaction = AsyncMock(return_value=True)
    adapter.bot_api10.delete_all_message_reactions = AsyncMock(return_value=True)

    one = await adapter.clear_message_reactions(-100123, 55, user_id=777)
    assert one.success is True
    adapter.bot_api10.delete_message_reaction.assert_awaited_once_with(-100123, 55, 777)
    adapter.bot_api10.delete_all_message_reactions.assert_not_awaited()

    every = await adapter.clear_message_reactions(-100123, 55)
    assert every.success is True
    adapter.bot_api10.delete_all_message_reactions.assert_awaited_once_with(-100123, 55)


@pytest.mark.asyncio
async def test_fetch_user_personal_chat_messages_is_error_safe():
    adapter = TelegramNotificationAdapter("123456:fake-token")
    adapter.bot_api10 = MagicMock()
    adapter.bot_api10.get_user_personal_chat_messages = AsyncMock(
        return_value=[{"text": "salom"}]
    )
    assert await adapter.fetch_user_personal_chat_messages(777) == [{"text": "salom"}]

    adapter.bot_api10.get_user_personal_chat_messages = AsyncMock(
        side_effect=RuntimeError("forbidden")
    )
    assert await adapter.fetch_user_personal_chat_messages(777) == []


@pytest.mark.asyncio
async def test_send_ephemeral_reply_forwards_receiver():
    adapter = TelegramNotificationAdapter("123456:fake-token")
    adapter.bot_api10 = MagicMock()
    adapter.bot_api10.send_ephemeral_message = AsyncMock(
        return_value={"message_id": 321}
    )

    result = await adapter.send_ephemeral_reply(-100500, "Faqat sizga", 777)

    assert result.success is True
    assert result.group_message_id == 321
    kwargs = adapter.bot_api10.send_ephemeral_message.await_args.kwargs
    assert kwargs["receiver_user_id"] == 777


@pytest.mark.asyncio
async def test_send_rich_group_message_requires_content():
    adapter = TelegramNotificationAdapter("123456:fake-token")
    adapter.bot_api10 = MagicMock()
    adapter.bot_api10.send_rich_message = AsyncMock(return_value={"message_id": 9})

    empty = await adapter.send_rich_group_message(-100500)
    assert empty.success is False
    adapter.bot_api10.send_rich_message.assert_not_awaited()

    ok = await adapter.send_rich_group_message(-100500, text="Salom")
    assert ok.success is True
    assert ok.group_message_id == 9
    rich_message = adapter.bot_api10.send_rich_message.await_args.args[1]
    assert rich_message == {"text": "Salom"}
