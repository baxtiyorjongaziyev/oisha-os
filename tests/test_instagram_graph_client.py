from __future__ import annotations

from types import SimpleNamespace

from pydantic import SecretStr

from src.services.core.instagram_agent import InstagramGraphClient


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _settings(**overrides):
    values = {
        "META_INSTAGRAM_USER_ID": "ig_123",
        "META_INSTAGRAM_ACCOUNT_ID": None,
        "META_PAGE_ID": "page_123",
        "META_PAGE_ACCESS_TOKEN": SecretStr("test-token"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_profile_request_is_read_only_and_does_not_return_token(monkeypatch):
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(url=url, params=params, timeout=timeout)
        return _Response({"id": "ig_123", "username": "baxtiyorjongaziyev"})

    monkeypatch.setattr("src.services.core.instagram_agent.requests.get", fake_get)
    client = InstagramGraphClient(_settings())

    result = client.get_profile()

    assert result["ok"] is True
    assert result["username"] == "baxtiyorjongaziyev"
    assert seen["url"].endswith("/v19.0/ig_123")
    assert seen["params"]["access_token"] == "test-token"
    assert "test-token" not in str(result)


def test_list_media_bounds_limit(monkeypatch):
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(url=url, params=params, timeout=timeout)
        return _Response({"data": []})

    monkeypatch.setattr("src.services.core.instagram_agent.requests.get", fake_get)
    client = InstagramGraphClient(_settings())

    result = client.list_media(limit=1000)

    assert result == {"data": [], "ok": True}
    assert seen["url"].endswith("/ig_123/media")
    assert seen["params"]["limit"] == 25


def test_missing_config_fails_closed_without_network(monkeypatch):
    def fail_get(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("src.services.core.instagram_agent.requests.get", fail_get)
    client = InstagramGraphClient(
        _settings(
            META_INSTAGRAM_USER_ID=None,
            META_INSTAGRAM_ACCOUNT_ID=None,
            META_PAGE_ACCESS_TOKEN=None,
        )
    )

    result = client.get_profile()

    assert result["ok"] is False
    assert result["error"] == "instagram_not_configured"
    assert result["missing"] == [
        "META_INSTAGRAM_USER_ID",
        "META_PAGE_ACCESS_TOKEN",
    ]


def test_graph_error_is_structured_and_token_safe(monkeypatch):
    def fake_get(url, params, timeout):
        return _Response(
            {
                "error": {
                    "message": "Unsupported get request",
                    "type": "GraphMethodException",
                    "code": 100,
                }
            },
            status_code=400,
        )

    monkeypatch.setattr("src.services.core.instagram_agent.requests.get", fake_get)
    result = InstagramGraphClient(_settings()).get_profile()

    assert result == {
        "ok": False,
        "error": "Unsupported get request",
        "error_type": "GraphMethodException",
        "error_code": 100,
        "status_code": 400,
    }
    assert "test-token" not in str(result)

