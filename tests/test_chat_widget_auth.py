import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from src.api.auth_service import issue_widget_jwt, decode_widget_jwt
from src.services.api_server.core import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-at-least-32-bytes-long-for-widget!")
    return TestClient(app)


def test_issue_and_decode_widget_jwt():
    secret = "test-secret-key-12345-that-is-at-least-32-bytes-long!"
    token = issue_widget_jwt(session_id="test_session_1", secret=secret, ttl_seconds=3600)
    assert token is not None
    assert isinstance(token, str)

    payload = decode_widget_jwt(token, secret)
    assert payload is not None
    assert payload.get("sub") == "widget_test_session_1"
    assert payload.get("role") == "widget_guest"
    assert "chat:write" in payload.get("scopes", [])


def test_decode_widget_jwt_invalid_secret():
    secret = "test-secret-key-12345-that-is-at-least-32-bytes-long!"
    token = issue_widget_jwt(session_id="test_session_1", secret=secret, ttl_seconds=3600)
    payload = decode_widget_jwt(token, "wrong-secret-that-is-at-least-32-bytes-long-too!")
    assert payload is None


def test_chat_token_endpoint(client):
    res = client.post("/api/chat/token")
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert "session_id" in data


def test_chat_send_with_widget_token(client, monkeypatch):
    from src.agents.autonomous_sales_agent import AutonomousSalesAgent

    monkeypatch.setattr(
        AutonomousSalesAgent,
        "handle_incoming",
        AsyncMock(return_value={"response": "Assalomu alaykum! Sizga qanday yordam bera olaman?"}),
    )

    # 1. Get token
    token_res = client.post("/api/chat/token")
    assert token_res.status_code == 200
    token_data = token_res.json()
    token = token_data["token"]
    session_id = token_data["session_id"]

    # 2. Send message with Bearer token
    res = client.post(
        "/api/chat/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": session_id, "text": "Salom"},
    )
    assert res.status_code == 200
    assert res.json().get("status") == "success"
    assert "Assalomu alaykum" in res.json().get("response", "")


def test_chat_send_unauthorized(client):
    res = client.post(
        "/api/chat/send",
        headers={"Authorization": "Bearer invalid.jwt.token"},
        json={"user_id": "web_123", "text": "Salom"},
    )
    assert res.status_code == 401
