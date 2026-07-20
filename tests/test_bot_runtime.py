from types import SimpleNamespace

import pytest

from src.services.core.telegram.bot_runtime import (
    AiogramBotRuntime,
    TelethonBotRuntime,
    build_outbound_bot_runtime,
    build_bot_runtime,
)


class FakeTelethonClient:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text, **kwargs):
        self.calls.append((chat_id, text, kwargs))
        return SimpleNamespace(id=101)


class FakeAiogramBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message_id=202)


@pytest.mark.asyncio
async def test_telethon_runtime_keeps_current_send_message_shape():
    client = FakeTelethonClient()
    runtime = TelethonBotRuntime(client)

    sent = await runtime.send_message(
        -1001,
        "salom",
        parse_mode="HTML",
        message_thread_id=77,
        disable_web_page_preview=True,
        disable_notification=True,
    )

    assert sent.backend == "telethon"
    assert sent.message_id == 101
    assert client.calls == [
        (
            -1001,
            "salom",
            {
                "parse_mode": "html",
                "reply_to": 77,
                "link_preview": False,
                "silent": True,
            },
        )
    ]


@pytest.mark.asyncio
async def test_aiogram_runtime_uses_bot_api_names():
    bot = FakeAiogramBot()
    runtime = AiogramBotRuntime(bot)

    sent = await runtime.send_message(
        -1001,
        "salom",
        parse_mode="HTML",
        message_thread_id=77,
        disable_notification=True,
    )

    assert sent.backend == "aiogram"
    assert sent.message_id == 202
    assert bot.calls == [
        {
            "chat_id": -1001,
            "text": "salom",
            "parse_mode": "HTML",
            "message_thread_id": 77,
            "disable_notification": True,
        }
    ]


@pytest.mark.asyncio
async def test_aiogram_runtime_converts_telethon_style_buttons():
    bot = FakeAiogramBot()
    runtime = AiogramBotRuntime(bot)

    await runtime.send_message(
        -1001,
        "tasdiq",
        buttons=[[{"text": "OK", "data": b"approve:1"}]],
        reply_to=55,
    )

    call = bot.calls[0]
    assert call["reply_to_message_id"] == 55
    assert "buttons" not in call
    assert "reply_markup" in call


def test_bot_runtime_factory_rejects_unknown_backend():
    assert isinstance(build_bot_runtime(backend="telethon", client=object()), TelethonBotRuntime)
    assert isinstance(build_bot_runtime(backend="aiogram", client=object()), AiogramBotRuntime)

    with pytest.raises(ValueError, match="Unsupported bot runtime backend"):
        build_bot_runtime(backend="raw", client=object())


def test_outbound_runtime_defaults_to_telethon_send_only():
    client = object()
    runtime = build_outbound_bot_runtime(
        backend="",
        bot_token="token",
        telethon_client=client,
    )

    assert isinstance(runtime, TelethonBotRuntime)
    assert runtime.client is client


def test_outbound_runtime_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unsupported bot runtime backend"):
        build_outbound_bot_runtime(
            backend="polling",
            bot_token="token",
            telethon_client=object(),
        )
