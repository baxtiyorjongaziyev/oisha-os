"""Personal Google Drive OAuth onboarding security tests (no Google calls)."""
from __future__ import annotations

import asyncio
import os
import stat
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.core.crm import drive_oauth_onboarding as oauth


def test_credentials_not_issued_without_client(monkeypatch):
    for name in (
        "GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GDRIVE_OFFLOAD_FOLDER_ID", "root123")
    assert oauth.oauth_client_ready() is False
    with pytest.raises(RuntimeError):
        asyncio.run(oauth.issue_owner_link())


def test_oauth_link_requires_one_time_ticket(monkeypatch):
    monkeypatch.setattr(oauth, "oauth_client_ready", lambda: True)
    monkeypatch.setattr(oauth, "_consume", AsyncMock(return_value=False))
    monkeypatch.setattr(oauth, "_flow", Mock())
    with pytest.raises(PermissionError):
        asyncio.run(oauth.begin_authorization("expired"))
    oauth._flow.assert_not_called()


def test_oauth_google_url_has_offline_consent(monkeypatch):
    monkeypatch.setattr(oauth, "oauth_client_ready", lambda: True)
    monkeypatch.setattr(oauth, "_consume", AsyncMock(return_value=True))
    monkeypatch.setattr(oauth, "_issue", AsyncMock(return_value="state-123"))
    flow = Mock()
    flow.authorization_url.return_value = ("https://accounts.google.com/oauth", "state-123")
    monkeypatch.setattr(oauth, "_flow", lambda: flow)
    uri = asyncio.run(oauth.begin_authorization("ticket-123"))
    assert uri.startswith("https://accounts.google.com/")
    kwargs = flow.authorization_url.call_args.kwargs
    assert kwargs["state"] == "state-123"
    assert kwargs["access_type"] == "offline"
    assert kwargs["prompt"] == "consent"


def test_reject_wrong_google_account_before_drive_access(monkeypatch):
    monkeypatch.setenv("GDRIVE_EXPECTED_EMAIL", "baxtiyorjongaziyev@gmail.com")
    response = Mock()
    response.json.return_value = {
        "email": "wrong@example.com", "email_verified": True,
    }
    monkeypatch.setattr(oauth.requests, "get", Mock(return_value=response))
    drive = Mock()
    monkeypatch.setattr(oauth, "build", drive)
    with pytest.raises(PermissionError, match="not the approved"):
        oauth._validate_google_account(SimpleNamespace(token="test_token"))
    drive.assert_not_called()


def test_refuse_non_5tb_quota(monkeypatch):
    monkeypatch.setenv("GDRIVE_EXPECTED_EMAIL", "baxtiyorjongaziyev@gmail.com")
    response = Mock()
    response.json.return_value = {
        "email": "baxtiyorjongaziyev@gmail.com", "email_verified": True,
    }
    monkeypatch.setattr(oauth.requests, "get", Mock(return_value=response))
    service = Mock()
    service.about.return_value.get.return_value.execute.return_value = {
        "user": {"emailAddress": "baxtiyorjongaziyev@gmail.com"},
        "storageQuota": {"limit": "15000000000"},
    }
    monkeypatch.setattr(oauth, "build", lambda *args, **kwargs: service)
    with pytest.raises(PermissionError, match="5 TB"):
        oauth._validate_google_account(SimpleNamespace(token="t"))
    service.files.assert_not_called()


def test_credentials_saved_privately_and_atomically(monkeypatch, tmp_path):
    path = tmp_path / "gdrive_token.json"
    monkeypatch.setenv("GDRIVE_OAUTH_TOKEN_FILE", str(path))
    oauth._persist(SimpleNamespace(to_json=lambda: '{"refresh_token": "test"}'))
    assert path.read_text() == '{"refresh_token": "test"}'
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_invalid_oauth_state_never_exchanges_code(monkeypatch):
    monkeypatch.setattr(oauth, "_consume", AsyncMock(return_value=False))
    monkeypatch.setattr(oauth, "_flow", Mock())
    with pytest.raises(PermissionError):
        asyncio.run(oauth.complete_authorization("invalid", "code"))
    oauth._flow.assert_not_called()


def test_crm_sync_refuses_missing_personal_oauth(monkeypatch, tmp_path):
    """Even a manual migration must not fall back to a service account."""
    import sys
    from scripts import safe_crm_drive_sync as runner
    from src.settings import settings

    monkeypatch.setattr(settings, "GDRIVE_OFFLOAD_FOLDER_ID", "root123")
    monkeypatch.setattr(oauth, "token_path", lambda: tmp_path / "not-authorized.json")
    monkeypatch.setattr(sys, "argv", ["safe_crm_drive_sync.py", "--preflight"])
    fake_drive = Mock()
    monkeypatch.setattr(runner, "GoogleDriveSync", fake_drive)

    with pytest.raises(SystemExit) as stop:
        asyncio.run(runner.main())
    assert stop.value.code == 2
    fake_drive.assert_not_called()
