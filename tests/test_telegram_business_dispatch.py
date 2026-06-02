from src import api_server


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
        api_server.business_connections,
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
        api_server.business_connections,
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
