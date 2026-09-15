import pytest

from src import api_server
from src.services.api_server.webhooks import process_telegram_ai_update


def test_bot_to_bot_is_disabled_in_production_by_default(monkeypatch):
    monkeypatch.setattr(api_server.settings, "TELEGRAM_BOT_TO_BOT_ENABLED", False)

    reason = api_server._bot2bot_skip_reason(
        {"id": 99, "is_bot": True},
        chat_id=77,
    )

    assert reason == "disabled"


def test_bot_to_bot_round_limit_is_conservative():
    assert api_server.BOT2BOT_MAX_ROUNDS == 1
    assert api_server.BOT2BOT_COOLDOWN_SEC == 300


def test_bot_to_bot_allows_one_round_then_rate_limits(monkeypatch):
    monkeypatch.setattr(api_server.settings, "TELEGRAM_BOT_TO_BOT_ENABLED", True)
    api_server._bot2bot_tracker.clear()
    from_user = {"id": 99, "is_bot": True}

    assert api_server._bot2bot_skip_reason(from_user, chat_id=77) == ""
    assert api_server._bot2bot_skip_reason(from_user, chat_id=77) == "rate_limit"


def test_business_loop_filter_skips_messages_sent_by_business_bot():
    reason = api_server._business_message_skip_reason(
        {
            "business_connection_id": "biz-1",
            "from": {"id": 42},
            "sender_business_bot": {"id": 99, "is_bot": True},
        }
    )

    assert reason == "sender_business_bot"


def test_business_loop_filter_skips_owner_authored_messages(monkeypatch):
    monkeypatch.setitem(
        api_server.api_state.business_connections,
        "biz-owner",
        {"user_id": 42, "user_name": "Owner", "can_reply": True},
    )
    monkeypatch.setattr(api_server.settings, "OWNER_ID", 0)

    reason = api_server._business_message_skip_reason(
        {
            "business_connection_id": "biz-owner",
            "from": {"id": 42},
        }
    )

    assert reason == "business_owner"


def test_business_loop_filter_allows_incoming_client_messages(monkeypatch):
    monkeypatch.setitem(
        api_server.api_state.business_connections,
        "biz-client",
        {"user_id": 42, "user_name": "Owner", "can_reply": True},
    )
    monkeypatch.setattr(api_server.settings, "OWNER_ID", 42)

    reason = api_server._business_message_skip_reason(
        {
            "business_connection_id": "biz-client",
            "from": {"id": 77},
        }
    )

    assert reason == ""


def test_business_loop_filter_skips_stale_backlog(monkeypatch):
    monkeypatch.setattr(api_server.settings, "OWNER_ID", 42)

    reason = api_server._business_message_skip_reason(
        {
            "business_connection_id": "biz-stale",
            "from": {"id": 77},
            "date": 1,
        }
    )

    assert reason == "stale_backlog"


@pytest.mark.asyncio
async def test_business_connection_update_stores_connection(monkeypatch):
    from src.api.routes.state import api_state

    api_state.business_connections.pop("conn-1", None)

    result = await process_telegram_ai_update(
        {
            "update_id": 1,
            "business_connection": {"id": "conn-1", "user_id": 42, "is_enabled": True},
        }
    )

    assert result == {"ok": True, "handled": True, "update_type": "business_connection"}
    assert api_state.business_connections["conn-1"]["user_id"] == 42


@pytest.mark.asyncio
async def test_business_connection_update_removes_disabled_connection(monkeypatch):
    from src.api.routes.state import api_state

    api_state.business_connections["conn-2"] = {"user_id": 42}

    result = await process_telegram_ai_update(
        {
            "update_id": 2,
            "business_connection": {"id": "conn-2", "user_id": 42, "is_enabled": False},
        }
    )

    assert result["handled"] is True
    assert "conn-2" not in api_state.business_connections


@pytest.mark.asyncio
async def test_business_message_skipped_by_loop_filter_is_not_replied_to(monkeypatch):
    monkeypatch.setattr(api_server.settings, "OWNER_ID", 42)

    result = await process_telegram_ai_update(
        {
            "update_id": 3,
            "business_message": {
                "business_connection_id": "conn-3",
                "from": {"id": 42},
                "chat": {"id": 42},
                "text": "salom",
            },
        }
    )

    assert result == {"handled": False, "reason": "business_owner"}


@pytest.mark.asyncio
async def test_business_message_replies_via_business_connection_id(monkeypatch):
    monkeypatch.setattr(api_server.settings, "OWNER_ID", 999)

    sent_calls = []

    class _FakeClient:
        def __init__(self, token):
            self.token = token

        async def call(self, method, payload):
            sent_calls.append((method, payload))
            return {"message_id": 1}

    monkeypatch.setattr(
        "src.services.core.telegram.telegram_ai_features.TelegramBotAPI10Client",
        _FakeClient,
    )

    async def _fake_handle_openclaw_message(**kwargs):
        return "Salom, qanday yordam bera olaman?"

    import src.openclaw_bridge as openclaw_bridge

    monkeypatch.setattr(
        openclaw_bridge, "handle_openclaw_message", _fake_handle_openclaw_message
    )

    result = await process_telegram_ai_update(
        {
            "update_id": 4,
            "business_message": {
                "business_connection_id": "conn-4",
                "from": {"id": 77},
                "chat": {"id": 77},
                "text": "Narxi qancha?",
            },
        }
    )

    assert result["ok"] is True
    assert result["update_type"] == "business_message"
    assert sent_calls == [
        (
            "sendMessage",
            {
                "business_connection_id": "conn-4",
                "chat_id": 77,
                "text": "Salom, qanday yordam bera olaman?",
            },
        )
    ]


@pytest.mark.asyncio
async def test_business_message_without_agent_response_is_not_handled(monkeypatch):
    monkeypatch.setattr(api_server.settings, "OWNER_ID", 999)

    async def _empty_response(**kwargs):
        return ""

    import src.openclaw_bridge as openclaw_bridge

    monkeypatch.setattr(openclaw_bridge, "handle_openclaw_message", _empty_response)

    result = await process_telegram_ai_update(
        {
            "update_id": 5,
            "business_message": {
                "business_connection_id": "conn-5",
                "from": {"id": 77},
                "chat": {"id": 77},
                "text": "salom",
            },
        }
    )

    assert result == {"handled": False, "reason": "empty_agent_response"}
