import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.services.api_server.core import app
from src.services.api_server.oauth import _OAuthSessionStore


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_oauth_session_store():
    store = _OAuthSessionStore()
    await store.set("state_123", "verifier_abc", ttl=10)
    val = await store.get("state_123")
    assert val == "verifier_abc"

    await store.delete("state_123")
    assert await store.get("state_123") is None


def test_airtable_login_redirect(client, monkeypatch):
    monkeypatch.setenv("AIRTABLE_CLIENT_ID", "test_client_id")
    res = client.get("/api/auth/airtable/login", follow_redirects=False)
    assert res.status_code == 307
    location = res.headers.get("location", "")
    assert "airtable.com/oauth2/v1/authorize" in location
    assert "client_id=test_client_id" in location
    assert "code_challenge=" in location
    assert "state=" in location


def test_airtable_callback_missing_state(client):
    res = client.get("/api/auth/airtable/callback?code=some_code", follow_redirects=False)
    assert res.status_code == 400


def test_airtable_callback_invalid_state(client):
    res = client.get("/api/auth/airtable/callback?code=some_code&state=non_existent_state", follow_redirects=False)
    assert res.status_code == 400


def test_telegram_login_page(client):
    res = client.get("/api/auth/telegram/login")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")


def test_telegram_callback_fails_without_strong_jwt_secret(client, monkeypatch):
    from src.api import auth_service

    monkeypatch.setattr(auth_service, "verify_telegram_hash", lambda *args, **kwargs: True)
    monkeypatch.setattr(auth_service, "is_auth_date_fresh", lambda *args, **kwargs: True)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    params = {
        "id": "12345",
        "first_name": "Test",
        "username": "tester",
        "auth_date": "1700000000",
        "hash": "validhash",
    }
    res = client.get("/api/auth/telegram/callback", params=params)
    assert res.status_code == 503
    assert "JWT_SECRET" in res.json().get("detail", "")


def test_telegram_callback_success_with_strong_jwt_secret(client, monkeypatch):
    from src.api import auth_service

    monkeypatch.setattr(auth_service, "verify_telegram_hash", lambda *args, **kwargs: True)
    monkeypatch.setattr(auth_service, "is_auth_date_fresh", lambda *args, **kwargs: True)
    monkeypatch.setenv("JWT_SECRET", "test-dedicated-jwt-secret-at-least-32-bytes-long!")

    params = {
        "id": "12345",
        "first_name": "Test",
        "username": "tester",
        "auth_date": "1700000000",
        "hash": "validhash",
    }
    res = client.get("/api/auth/telegram/callback", params=params, follow_redirects=False)
    assert res.status_code == 307
    cookie = res.headers.get("set-cookie", "")
    assert "oisha_token=" in cookie
    assert "Max-Age=" in cookie or "max-age=" in cookie.lower()
