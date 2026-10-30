"""Credential selection tests use synthetic tokens only; no live requests."""

import json
from unittest.mock import Mock

import pytest

from src.services.core.crm.amocrm.auth import AmoCRMAuthMixin


class Client(AmoCRMAuthMixin):
    def __init__(self, path):
        self.token_file = str(path)
        self.token_data = {}
        self.access_token = None
        self.last_error = None
        self.auth_blocked_until = 0
        self.auth_block_reason = None
        self.base_url = "https://synthetic.example.test"
        self.client_id = "synthetic-client"
        self.client_secret = "synthetic-secret"
        self.redirect_url = "https://example.test/callback"
        self._persist_token_to_db = Mock()
        self._load_token_from_db_fallback = Mock(return_value=False)
        self._load_token()


@pytest.fixture
def sources(monkeypatch, tmp_path):
    monkeypatch.setenv("AMOCRM_ACCESS_TOKEN", "synthetic-long-lived")
    monkeypatch.setenv("AMOCRM_TOKEN_JSON", json.dumps({
        "access_token": "synthetic-json", "refresh_token": "synthetic-json-refresh",
    }))
    monkeypatch.setenv("AMOCRM_REFRESH_TOKEN", "synthetic-raw-refresh")
    monkeypatch.delenv("AMOCRM_TOKEN_SOURCE", raising=False)
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps({
        "access_token": "synthetic-file", "refresh_token": "synthetic-file-refresh",
    }))
    return path


@pytest.mark.parametrize("source,expected", [
    ("auto", "synthetic-long-lived"),
    ("long_lived", "synthetic-long-lived"),
    ("file", "synthetic-file"),
    ("env_json", "synthetic-json"),
])
def test_explicit_source_precedence(monkeypatch, sources, source, expected):
    monkeypatch.setenv("AMOCRM_TOKEN_SOURCE", source)
    client = Client(sources)
    assert client.access_token == expected
    client._load_token_from_db_fallback.assert_not_called()
    if source in {"auto", "long_lived", "file"}:
        client._persist_token_to_db.assert_not_called()


@pytest.mark.parametrize("source,content,error", [
    ("invalid-synthetic", "{}", "token_source_invalid"),
    ("file", "{}", "token_source_unavailable"),
    ("file", "not-json", "token_source_unavailable"),
    ("env_json", "{}", "token_source_unavailable"),
    ("long_lived", "{}", "token_source_unavailable"),
])
def test_selected_source_fails_closed(monkeypatch, sources, source, content, error):
    monkeypatch.setenv("AMOCRM_TOKEN_SOURCE", source)
    monkeypatch.setenv("AMOCRM_TOKEN_JSON", content)
    monkeypatch.setenv("AMOCRM_ACCESS_TOKEN", "")
    sources.write_text(content)
    client = Client(sources)
    assert client.access_token is None
    assert client.token_data == {}
    assert client.last_error == error
    client._load_token_from_db_fallback.assert_not_called()
    assert client._check_connection_sync() is False
    assert client.last_error == error


def test_missing_selected_file_does_not_use_other_credentials(monkeypatch, sources):
    monkeypatch.setenv("AMOCRM_TOKEN_SOURCE", "file")
    sources.unlink()
    client = Client(sources)
    assert client.last_error == "token_source_unavailable"
    assert client.access_token is None


def test_rejected_long_lived_does_not_refresh_or_fallback(monkeypatch, sources, capsys):
    import src.services.core.crm.amocrm.auth as auth

    client = Client(sources)
    response = Mock(status_code=401)
    response.json.return_value = {"detail": "synthetic-secret"}
    get = Mock(return_value=response)
    post = Mock()
    monkeypatch.setattr(auth.requests, "get", get)
    monkeypatch.setattr(auth.requests, "post", post)
    assert client._check_connection_sync() is False
    assert client.last_error == "long_lived_token_rejected_http_401"
    assert client.access_token == "synthetic-long-lived"
    get.assert_called_once()
    post.assert_not_called()
    response.json.assert_not_called()
    assert "synthetic-secret" not in capsys.readouterr().out


@pytest.mark.parametrize("exception", [False, True])
def test_refresh_rejection_never_logs_response_or_exception(monkeypatch, sources, exception):
    import src.services.core.crm.amocrm.auth as auth

    monkeypatch.setenv("AMOCRM_TOKEN_SOURCE", "file")
    client = Client(sources)
    response = Mock(status_code=401, text="synthetic-secret")
    response.json.return_value = {"detail": "synthetic-secret"}
    post = Mock(side_effect=RuntimeError("synthetic-secret")) if exception else Mock(return_value=response)
    monkeypatch.setattr(auth.requests, "post", post)
    logger = Mock()
    monkeypatch.setattr(auth, "logger", logger)
    assert client._do_http_refresh() is False
    assert "synthetic-secret" not in str(logger.mock_calls)
    response.json.assert_not_called()


def test_selected_oauth_rejection_does_not_switch_to_long_lived(monkeypatch, sources):
    import src.services.core.crm.amocrm.auth as auth

    monkeypatch.setenv("AMOCRM_TOKEN_SOURCE", "file")
    client = Client(sources)
    monkeypatch.setattr(auth.requests, "get", Mock(return_value=Mock(status_code=401)))
    refresh = Mock(return_value=False)
    monkeypatch.setattr(client, "refresh_token", refresh)
    assert client._check_connection_sync() is False
    assert client.access_token == "synthetic-file"
    refresh.assert_called_once()
