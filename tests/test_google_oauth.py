import json

from src.services.core.google_oauth import (
    GOOGLE_USER_SCOPES,
    load_user_credentials,
    save_user_credentials,
)

_TOKEN_PAYLOAD = {
    "token": "ya29.test",
    "refresh_token": "1//test",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "client-id.apps.googleusercontent.com",
    "client_secret": "client-secret",
    "scopes": list(GOOGLE_USER_SCOPES),
    "expiry": "2099-01-01T00:00:00Z",
}


class _FakeCredentials:
    def __init__(self, payload):
        self._payload = payload

    def to_json(self):
        return json.dumps(self._payload)


def test_save_user_credentials_writes_json_not_pickle(tmp_path):
    token_path = tmp_path / "token.json"

    assert save_user_credentials(str(token_path), _FakeCredentials(_TOKEN_PAYLOAD))

    raw = token_path.read_text(encoding="utf-8")
    assert raw.lstrip().startswith("{")
    assert json.loads(raw)["refresh_token"] == "1//test"


def test_load_user_credentials_reads_json_token(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps(_TOKEN_PAYLOAD), encoding="utf-8")

    credentials = load_user_credentials(str(token_path), GOOGLE_USER_SCOPES)

    assert credentials is not None
    assert credentials.token == "ya29.test"
    assert credentials.refresh_token == "1//test"


def test_load_user_credentials_ignores_legacy_pickle(tmp_path):
    token_path = tmp_path / "token.pickle"
    token_path.write_bytes(b"\x80\x04not-a-json-token")

    assert load_user_credentials(str(token_path), GOOGLE_USER_SCOPES) is None


def test_load_user_credentials_returns_none_for_broken_json(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{not json", encoding="utf-8")

    assert load_user_credentials(str(token_path), GOOGLE_USER_SCOPES) is None


def test_load_user_credentials_returns_none_when_expired_without_refresh(tmp_path):
    token_path = tmp_path / "token.json"
    payload = dict(_TOKEN_PAYLOAD)
    payload.pop("refresh_token")
    payload["expiry"] = "2020-01-01T00:00:00Z"
    token_path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_user_credentials(str(token_path), GOOGLE_USER_SCOPES) is None


def test_load_user_credentials_returns_none_when_file_missing(tmp_path):
    assert load_user_credentials(str(tmp_path / "missing.json")) is None
