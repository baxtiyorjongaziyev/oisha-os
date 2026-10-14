import pytest
from fastapi.testclient import TestClient

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
    from unittest.mock import MagicMock, AsyncMock
    from src.api import auth_service

    monkeypatch.setattr(auth_service, "verify_telegram_hash", lambda *args, **kwargs: True)
    monkeypatch.setattr(auth_service, "is_auth_date_fresh", lambda *args, **kwargs: True)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    mock_db = MagicMock()
    mock_db.users.upsert_user = AsyncMock()
    mock_db.users.get_user = AsyncMock(return_value={"role": "client"})
    monkeypatch.setattr("src.services.api_server.oauth.get_db", lambda: mock_db)

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
    from unittest.mock import MagicMock, AsyncMock
    from src.api import auth_service

    monkeypatch.setattr(auth_service, "verify_telegram_hash", lambda *args, **kwargs: True)
    monkeypatch.setattr(auth_service, "is_auth_date_fresh", lambda *args, **kwargs: True)
    monkeypatch.setenv("JWT_SECRET", "test-dedicated-jwt-secret-at-least-32-bytes-long!")

    mock_db = MagicMock()
    mock_db.users.upsert_user = AsyncMock()
    mock_db.users.get_user = AsyncMock(return_value={"role": "client"})
    monkeypatch.setattr("src.services.api_server.oauth.get_db", lambda: mock_db)

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


def test_telegram_login_redirect_sanitization(client):
    # Valid next in whitelist
    res = client.get("/api/auth/telegram/login?next=/api/marketing/capi/console")
    assert res.status_code == 200
    assert 'data-auth-url="/api/auth/telegram/callback?next=/api/marketing/capi/console"' in res.text

    # Malicious next not in whitelist
    res_bad = client.get('/api/auth/telegram/login?next=https://evil.com"><script>alert(1)</script>')
    assert res_bad.status_code == 200
    assert 'data-auth-url="/api/auth/telegram/callback"' in res_bad.text
    assert "<script>alert(1)</script>" not in res_bad.text


def test_telegram_callback_redirect_sanitization(client, monkeypatch):
    from unittest.mock import MagicMock, AsyncMock
    from src.api import auth_service

    monkeypatch.setattr(auth_service, "verify_telegram_hash", lambda *args, **kwargs: True)
    monkeypatch.setattr(auth_service, "is_auth_date_fresh", lambda *args, **kwargs: True)
    monkeypatch.setenv("JWT_SECRET", "test-dedicated-jwt-secret-at-least-32-bytes-long!")

    mock_db = MagicMock()
    mock_db.users.upsert_user = AsyncMock()
    mock_db.users.get_user = AsyncMock(return_value={"role": "client"})
    monkeypatch.setattr("src.services.api_server.oauth.get_db", lambda: mock_db)

    params = {
        "id": "12345",
        "first_name": "Test",
        "username": "tester",
        "auth_date": "1700000000",
        "hash": "validhash",
        "next": "/api/marketing/capi/console",
    }
    # Whitelisted next
    res = client.get("/api/auth/telegram/callback", params=params, follow_redirects=False)
    assert res.status_code == 307
    assert res.headers.get("location") == "/api/marketing/capi/console"

    # Malicious next not in whitelist
    params["next"] = "https://attacker.com/steal"
    res_malicious = client.get("/api/auth/telegram/callback", params=params, follow_redirects=False)
    assert res_malicious.status_code == 307
    assert res_malicious.headers.get("location") == "/"
