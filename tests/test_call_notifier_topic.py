"""Call analysis Telegram alert routes to its own topic via message_thread_id."""
from types import SimpleNamespace

import pytest

from src.services.core.calls import call_notifier


class FakeBotRuntime:
    def __init__(self):
        self.calls = []

    async def send_message(self, *, chat_id, text, **kwargs):
        self.calls.append({"chat_id": chat_id, "text": text, **kwargs})
        return SimpleNamespace(message_id=1)


@pytest.mark.asyncio
async def test_call_alert_uses_dedicated_topic_and_thread_id(monkeypatch):
    bot = FakeBotRuntime()
    monkeypatch.setattr(call_notifier, "app_ctx", SimpleNamespace(bot_runtime=bot), raising=False)

    import src.context as ctx
    monkeypatch.setattr(ctx, "app_ctx", SimpleNamespace(bot_runtime=bot), raising=False)

    from src.settings import settings
    monkeypatch.setattr(settings, "CALL_ANALYSIS_GROUP_ID", -1003854308552, raising=False)
    monkeypatch.setattr(settings, "CALL_ANALYSIS_TOPIC_ID", 548, raising=False)

    await call_notifier.send_call_analysis_telegram_alert(
        lead_id=123,
        call_id="c1",
        category="Boshqa",
        summary="Test xulosa",
        client_mood="Noaniq",
        next_steps="Ertaga uchrashuv",
        duration_seconds=90,
        manager_name="Aziz",
        caller_phone="+998881993333",
        analysis={},
        task_id=None,
    )

    assert len(bot.calls) == 1
    call = bot.calls[0]
    assert call["chat_id"] == -1003854308552
    assert call["message_thread_id"] == 548
    assert "reply_to_message_id" not in call
    assert "Test xulosa" in call["text"]


@pytest.mark.asyncio
async def test_call_alert_falls_back_to_amocrm_forward_topic(monkeypatch):
    bot = FakeBotRuntime()
    import src.context as ctx
    monkeypatch.setattr(ctx, "app_ctx", SimpleNamespace(bot_runtime=bot), raising=False)

    from src.settings import settings
    monkeypatch.setattr(settings, "CALL_ANALYSIS_GROUP_ID", None, raising=False)
    monkeypatch.setattr(settings, "CALL_ANALYSIS_TOPIC_ID", None, raising=False)
    monkeypatch.setattr(settings, "AMOCRM_ALERT_FORWARD_GROUP_ID", -100999, raising=False)
    monkeypatch.setattr(settings, "AMOCRM_ALERT_FORWARD_TOPIC_ID", 443, raising=False)

    await call_notifier.send_call_analysis_telegram_alert(
        lead_id=1, call_id="c2", category="Boshqa", summary="x", client_mood="Noaniq",
        next_steps="-", duration_seconds=10, manager_name="", caller_phone="",
        analysis={}, task_id=None,
    )

    assert bot.calls[0]["chat_id"] == -100999
    assert bot.calls[0]["message_thread_id"] == 443
