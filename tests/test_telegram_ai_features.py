import asyncio

import pytest

from src.services.core.telegram_ai_features import (
    BOT_API_10_ALLOWED_UPDATES,
    TelegramBotAPI10Client,
    TelegramBotAPIError,
    TelegramBotAPILongPoller,
    build_live_feature_status,
    build_offline_feature_status,
    build_text_article_result,
    classify_update,
    extract_guest_message_context,
    feature_matrix_payload,
)


def test_feature_matrix_covers_telegram_ai_revolution_capabilities():
    keys = {item["key"] for item in feature_matrix_payload()}

    assert "guest_mode" in keys
    assert "bot_to_bot" in keys
    assert "streaming_responses" in keys
    assert "chat_automation" in keys
    assert "managed_bots" in keys
    assert "private_topics" in keys
    assert "profile_context" in keys
    assert "monetization" in keys
    assert "moderation_and_polls" in keys
    assert "custom_ai_styles" in keys
    assert "emoji_sticker_search" in keys
    assert "poll_statistics" in keys
    assert "silent_scheduled_messages" in keys

    assert "guest_message" in BOT_API_10_ALLOWED_UPDATES
    assert "business_message" in BOT_API_10_ALLOWED_UPDATES
    assert "managed_bot" in BOT_API_10_ALLOWED_UPDATES


def test_extract_guest_message_context():
    update = {
        "update_id": 77,
        "guest_message": {
            "message_id": 10,
            "guest_query_id": "guest-query-1",
            "text": "@jonairobot brifni tekshir",
            "guest_bot_caller_user": {"id": 42, "first_name": "Ali"},
            "guest_bot_caller_chat": {"id": -1001, "title": "Sales"},
        },
    }

    ctx = extract_guest_message_context(update)

    assert ctx is not None
    assert ctx.update_id == 77
    assert ctx.guest_query_id == "guest-query-1"
    assert ctx.text == "@jonairobot brifni tekshir"
    assert ctx.caller_user["id"] == 42
    assert classify_update(update) == "guest_message"


def test_extract_guest_message_context_requires_query_id():
    assert extract_guest_message_context({"guest_message": {"text": "hi"}}) is None
    assert classify_update({"unknown": {}}) == "unknown"


def test_build_text_article_result_is_valid_inline_article():
    result = build_text_article_result("Assalomu alaykum", result_id="fixed")

    assert result["type"] == "article"
    assert result["id"] == "fixed"
    assert result["input_message_content"]["message_text"] == "Assalomu alaykum"
    assert result["input_message_content"]["link_preview_options"] == {
        "is_disabled": True
    }


@pytest.mark.asyncio
async def test_raw_client_answer_guest_query_uses_bot_api_10_payload():
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        return {"ok": True, "result": {"inline_message_id": "inline-1"}}

    client = TelegramBotAPI10Client("token", transport=transport)
    result = await client.answer_guest_query(
        "guest-query-1",
        build_text_article_result("Javob"),
    )

    assert result == {"inline_message_id": "inline-1"}
    assert calls[0][0] == "answerGuestQuery"
    assert calls[0][1]["guest_query_id"] == "guest-query-1"
    assert calls[0][1]["result"]["type"] == "article"


@pytest.mark.asyncio
async def test_raw_client_strips_none_values_and_streams_draft():
    calls = []

    async def transport(method, payload):
        calls.append((method, payload))
        return {"ok": True, "result": True}

    client = TelegramBotAPI10Client("token", transport=transport)
    sent = await client.send_message_draft(
        123,
        456,
        text="",
        message_thread_id=None,
        parse_mode=None,
    )

    assert sent is True
    assert calls == [
        (
            "sendMessageDraft",
            {"chat_id": 123, "draft_id": 456, "text": ""},
        )
    ]


@pytest.mark.asyncio
async def test_raw_client_raises_structured_error():
    async def transport(method, payload):
        return {
            "ok": False,
            "error_code": 429,
            "description": "Too Many Requests",
            "parameters": {"retry_after": 3},
        }

    client = TelegramBotAPI10Client("token", transport=transport)

    with pytest.raises(TelegramBotAPIError) as exc:
        await client.get_me()

    assert exc.value.method == "getMe"
    assert exc.value.error_code == 429
    assert exc.value.parameters["retry_after"] == 3


def test_feature_status_helpers():
    offline = build_offline_feature_status()
    live = build_live_feature_status(
        {
            "supports_guest_queries": True,
            "can_connect_to_business": True,
            "has_topics_enabled": False,
            "can_manage_bots": True,
        }
    )

    assert offline["bot_api_version_target"] == "10.0"
    assert offline["code_ready"]["guest_mode"] is True
    assert live["guest_mode"] is True
    assert live["business_chat_automation"] is True
    assert live["private_topics"] is False
    assert live["managed_bots"] is True


@pytest.mark.asyncio
async def test_long_poller_dispatches_raw_feature_updates_and_advances_offset():
    dispatched = []

    async def handler(update):
        dispatched.append(update)

    class FakeClient:
        async def get_updates(self, **kwargs):
            assert kwargs["offset"] is None
            return [
                {"update_id": 10, "message": {"text": "ordinary"}},
                {"update_id": 11, "guest_message": {"guest_query_id": "g1"}},
                {"update_id": 12, "business_connection": {"id": "biz1"}},
            ]

    poller = TelegramBotAPILongPoller("token", handler, client=FakeClient())
    stats = await poller.poll_once()

    assert stats == {"received": 3, "dispatched": 2}
    assert poller.offset == 13
    assert [item["update_id"] for item in dispatched] == [11, 12]


@pytest.mark.asyncio
async def test_running_long_poller_acknowledges_updates_before_slow_handler_finishes():
    release = asyncio.Event()
    started = asyncio.Event()
    offsets = []

    async def handler(update):
        started.set()
        await release.wait()

    class FakeClient:
        async def get_updates(self, **kwargs):
            offsets.append(kwargs["offset"])
            if len(offsets) == 1:
                return [{"update_id": 10, "business_message": {"text": "slow"}}]
            return []

    poller = TelegramBotAPILongPoller("token", handler, client=FakeClient())
    poller._start_workers()
    try:
        stats = await poller.poll_once()
        await started.wait()
        await poller.poll_once()

        assert stats == {"received": 1, "dispatched": 1}
        assert offsets == [None, 11]
    finally:
        release.set()
        assert poller._queue is not None
        await poller._queue.join()
        await poller._stop_workers()
