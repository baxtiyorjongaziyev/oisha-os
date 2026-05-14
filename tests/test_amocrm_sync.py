import json

import pytest

from src.services.core.amocrm_sync import AmoCRMSync


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_check_connection_uses_env_token(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "valid-access-token", "refresh_token": "refresh-token"}),
    )

    seen_headers = {}

    def fake_get(url, headers=None, timeout=None):
        seen_headers.update(headers or {})
        assert url == "https://jonbrandingagency.amocrm.ru/api/v4/account"
        assert timeout == 15
        return _Response(200, {"id": 1})

    monkeypatch.setattr("requests.get", fake_get)

    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    assert await amocrm.check_connection() is True
    assert seen_headers["Authorization"] == "Bearer valid-access-token"
    assert amocrm.last_error is None


@pytest.mark.asyncio
async def test_check_connection_refreshes_expired_token(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "expired-token", "refresh_token": "refresh-token"}),
    )

    calls = {"account": 0}

    def fake_get(url, headers=None, timeout=None):
        calls["account"] += 1
        return _Response(401 if calls["account"] == 1 else 200, {"id": 1})

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(AmoCRMSync, "refresh_token", lambda self: setattr(self, "access_token", "new-token") or True)

    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    assert await amocrm.check_connection() is True
    assert calls["account"] == 2
    assert amocrm.last_error is None


@pytest.mark.asyncio
async def test_invalid_oauth_refresh_blocks_repeated_crm_calls(monkeypatch):
    monkeypatch.setenv(
        "AMOCRM_TOKEN_JSON",
        json.dumps({"access_token": "expired-token", "refresh_token": "bad-refresh-token"}),
    )

    calls = {"post": 0, "get": 0}

    def fake_post(url, json=None, data=None, timeout=None):
        calls["post"] += 1
        return _Response(400, {"detail": "invalid oauth parameters"})

    def fake_get(url, headers=None, timeout=None):
        calls["get"] += 1
        return _Response(401, {"detail": "unauthorized"})

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    amocrm = AmoCRMSync("jonbrandingagency", "client-id", "client-secret", "https://example.test/cb")

    assert amocrm.refresh_token() is False
    assert amocrm.is_auth_blocked() is True
    assert calls["post"] == 2  # JSON attempt + form fallback before circuit opens.

    assert amocrm.refresh_token() is False
    assert await amocrm.check_connection() is False
    assert calls["post"] == 2
    assert calls["get"] == 0
