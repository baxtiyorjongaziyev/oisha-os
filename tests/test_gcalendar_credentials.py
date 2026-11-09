from unittest.mock import MagicMock, patch

from src.services.core.gcalendar import GoogleCalendarSync

ENV_NAME = "GOOGLE_CALENDAR_CREDENTIALS_PATH"


def _build_sync(monkeypatch, tmp_path, credentials_path, env_value=None):
    if env_value is None:
        monkeypatch.delenv(ENV_NAME, raising=False)
    else:
        monkeypatch.setenv(ENV_NAME, env_value)

    with patch(
        "src.services.core.gcalendar.load_user_credentials", return_value=None
    ), patch(
        "src.services.core.gcalendar.ServiceAccountCredentials"
    ) as creds_cls, patch(
        "src.services.core.gcalendar.build"
    ) as build_mock:
        creds_cls.from_service_account_file.return_value = MagicMock()
        build_mock.return_value = MagicMock()
        GoogleCalendarSync(credentials_path=str(credentials_path))

    return creds_cls.from_service_account_file


def test_env_credentials_path_checked_first(monkeypatch, tmp_path):
    default_key = tmp_path / "default.json"
    default_key.write_text("{}", encoding="utf-8")
    env_key = tmp_path / "calendar_key.json"
    env_key.write_text("{}", encoding="utf-8")

    from_service_account_file = _build_sync(
        monkeypatch, tmp_path, default_key, env_value=str(env_key)
    )

    assert from_service_account_file.call_args[0][0] == str(env_key)


def test_default_credentials_path_used_without_env(monkeypatch, tmp_path):
    default_key = tmp_path / "default.json"
    default_key.write_text("{}", encoding="utf-8")

    from_service_account_file = _build_sync(monkeypatch, tmp_path, default_key)

    assert from_service_account_file.call_args[0][0] == str(default_key)


def test_missing_env_path_falls_back_to_default(monkeypatch, tmp_path):
    default_key = tmp_path / "default.json"
    default_key.write_text("{}", encoding="utf-8")
    missing_key = tmp_path / "missing.json"

    from_service_account_file = _build_sync(
        monkeypatch, tmp_path, default_key, env_value=str(missing_key)
    )

    assert from_service_account_file.call_args[0][0] == str(default_key)
