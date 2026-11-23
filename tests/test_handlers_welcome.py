import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.core.dispatcher.handlers_welcome import (
    build_owner_notice,
    build_welcome_text,
    handle_write_access_allowed,
)


def _msg(uid=5, first="Ali", username="ali"):
    bot = SimpleNamespace(send_message=AsyncMock())
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid, first_name=first, username=username),
        answer=AsyncMock(),
        bot=bot,
    )


def test_welcome_text_with_and_without_name():
    assert ", Ali!" in build_welcome_text("Ali")
    assert "alaykum!" in build_welcome_text(None)


def test_owner_notice():
    text = build_owner_notice(SimpleNamespace(id=7, first_name="Vali", username=None))
    assert "Vali" in text and "id 7" in text and "@" not in text


def test_greets_user_and_notifies_owner():
    m = _msg()
    asyncio.run(handle_write_access_allowed(m, owner_id=1))
    m.answer.assert_awaited_once()
    m.bot.send_message.assert_awaited_once()
    assert m.bot.send_message.await_args.args[0] == 1


def test_owner_not_notified_about_self():
    m = _msg(uid=1)
    asyncio.run(handle_write_access_allowed(m, owner_id=1))
    m.bot.send_message.assert_not_awaited()


def test_send_failure_skips_owner_notice():
    m = _msg()
    m.answer.side_effect = RuntimeError("blocked")
    asyncio.run(handle_write_access_allowed(m, owner_id=1))
    m.bot.send_message.assert_not_awaited()
