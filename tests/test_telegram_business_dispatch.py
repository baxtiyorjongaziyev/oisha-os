from src import api_server


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
