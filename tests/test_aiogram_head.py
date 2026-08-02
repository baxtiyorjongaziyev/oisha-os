import asyncio

import pytest

from src.services.core.telegram.aiogram_head import AiogramBotHead


class _Session:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _Bot:
    def __init__(self):
        self.session = _Session()
        self.webhook_deleted = False

    async def delete_webhook(self, *, drop_pending_updates=False):
        assert drop_pending_updates is False
        self.webhook_deleted = True


class _Dispatcher:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.stopped = False
        self.kwargs = None

    async def start_polling(self, bot, **kwargs):
        self.kwargs = kwargs
        self.started.set()
        await self.release.wait()

    async def stop_polling(self):
        self.stopped = True
        self.release.set()


@pytest.mark.asyncio
async def test_aiogram_head_owns_polling_and_shutdown():
    bot = _Bot()
    dispatcher = _Dispatcher()
    head = AiogramBotHead(bot=bot, dispatcher=dispatcher)

    first = head.start()
    second = head.start()
    await dispatcher.started.wait()

    assert first is second
    assert head.running is True
    assert bot.webhook_deleted is True
    assert dispatcher.kwargs == {
        "handle_signals": False,
        "close_bot_session": False,
        "allowed_updates": None,
    }

    await head.stop()

    assert dispatcher.stopped is True
    assert bot.session.closed is True
    assert head.running is False
