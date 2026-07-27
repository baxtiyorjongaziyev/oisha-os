from datetime import datetime, timezone

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from telethon import events

from src.services.core.telegram.aiogram_telethon_compat import (
    AiogramTelethonCompatClient,
)


def _message(text: str) -> Message:
    return Message(
        message_id=10,
        date=datetime.now(timezone.utc),
        chat=Chat(id=99, type="private"),
        from_user=User(id=42, is_bot=False, first_name="Owner"),
        text=text,
    )


@pytest.mark.asyncio
async def test_compat_dispatches_specific_and_catch_all_message_handlers():
    bot = Bot("123456:ABCDEF_fake_token_for_tests")
    dispatcher = Dispatcher()
    client = AiogramTelethonCompatClient(bot=bot, dispatcher=dispatcher)
    seen = []

    @client.on(events.NewMessage(pattern=r"(?i)^/search(?:\s+(.+))?"))
    async def _specific(event):
        seen.append(("specific", event.pattern_match.group(1), event.sender_id))

    @client.on(events.NewMessage())
    async def _catch_all(event):
        seen.append(("all", event.text, event.is_private))

    client.attach()
    await dispatcher.feed_update(
        bot,
        Update(update_id=1, message=_message("/search 998901234567")),
    )
    await bot.session.close()

    assert seen == [
        ("specific", "998901234567", 42),
        ("all", "/search 998901234567", True),
    ]


@pytest.mark.asyncio
async def test_compat_dispatches_callback_with_telethon_data_shape():
    bot = Bot("123456:ABCDEF_fake_token_for_tests")
    dispatcher = Dispatcher()
    client = AiogramTelethonCompatClient(bot=bot, dispatcher=dispatcher)
    seen = []

    @client.on(events.CallbackQuery())
    async def _callback(event):
        seen.append((event.data.decode(), event.sender_id))

    client.attach()
    callback = CallbackQuery(
        id="callback-1",
        from_user=User(id=42, is_bot=False, first_name="Owner"),
        chat_instance="instance",
        data="approve:123",
        message=_message("Approval"),
    )
    await dispatcher.feed_update(
        bot,
        Update(update_id=2, callback_query=callback),
    )
    await bot.session.close()

    assert seen == [("approve:123", 42)]
