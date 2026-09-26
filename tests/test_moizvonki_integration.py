import asyncio
from unittest.mock import MagicMock, patch
import pytest
import requests
from pydantic import SecretStr

from src.services.call_analytics.transcriber import CallTranscriberMixin
from src.settings import AppSettings


class DummyAnalyzer(CallTranscriberMixin):
    def __init__(self, settings_obj=None):
        self._settings = settings_obj or AppSettings()
        self._moizvonki_session = None
        self.amocrm = MagicMock()
        self.amocrm.subdomain = "jonbranding"
        self.db = MagicMock()


def test_settings_moizvonki_defaults():
    settings = AppSettings()
    assert hasattr(settings, "MOIZVONKI_DOMAIN")
    assert settings.MOIZVONKI_DOMAIN == "jonbrandingagency.moizvonki.ru"


def test_login_moizvonki_missing_credentials():
    analyzer = DummyAnalyzer()
    analyzer._settings.MOIZVONKI_EMAIL = None
    analyzer._settings.MOIZVONKI_PASSWORD = None
    with patch.dict("os.environ", {}, clear=True):
        session = analyzer._login_moizvonki()
        assert session is None


def test_login_moizvonki_success_with_domain():
    analyzer = DummyAnalyzer()
    analyzer._settings.MOIZVONKI_EMAIL = "test@agency.uz"
    analyzer._settings.MOIZVONKI_PASSWORD = SecretStr("secretpass")
    analyzer._settings.MOIZVONKI_DOMAIN = "custom.moizvonki.ru"

    mock_resp_get = MagicMock()
    mock_resp_get.text = '<input type="hidden" name="csrfmiddlewaretoken" value="dummy_csrf_token">'
    mock_resp_get.status_code = 200

    mock_resp_post = MagicMock()
    mock_resp_post.status_code = 200

    with patch("requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.cookies = {"csrftoken": "dummy_csrf_token", "sessionid": "sess_123"}
        mock_session.get.return_value = mock_resp_get
        mock_session.post.return_value = mock_resp_post
        mock_session_cls.return_value = mock_session

        res = analyzer._login_moizvonki()
        assert res is not None
        mock_session.get.assert_called_with("https://custom.moizvonki.ru/accounts/login/", timeout=30)
        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        assert args[0] == "https://custom.moizvonki.ru/accounts/login/"
        assert kwargs["data"]["username"] == "test@agency.uz"
        assert kwargs["data"]["password"] == "secretpass"


@pytest.mark.asyncio
async def test_fetch_audio_bytes_ssl_retry():
    analyzer = DummyAnalyzer()
    analyzer._settings.MOIZVONKI_EMAIL = "test@agency.uz"
    analyzer._settings.MOIZVONKI_PASSWORD = SecretStr("secretpass")

    fake_session = MagicMock()
    resp_success = MagicMock()
    resp_success.status_code = 200
    resp_success.content = b"fake-audio-binary-data" * 10
    resp_success.headers = {"Content-Type": "audio/mpeg"}

    # First call raises SSLError, second call returns 200 OK
    fake_session.get.side_effect = [
        requests.exceptions.SSLError("SSLEOFError: unexpected eof"),
        resp_success,
    ]
    analyzer._moizvonki_session = fake_session

    result = await analyzer._fetch_audio_bytes("https://jonbrandingagency.moizvonki.ru/calls/recordings/test.mp3")
    assert result is not None
    audio_bytes, mime = result
    assert audio_bytes == b"fake-audio-binary-data" * 10
    assert mime == "audio/mpeg"
    assert fake_session.get.call_count == 2
