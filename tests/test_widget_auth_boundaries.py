"""Security regression tests for anonymous web-widget authentication."""
from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

from src.api.auth_service import issue_widget_jwt
from src.api.routes.chat_widget import (
    _get_widget_jwt_secret,
    _require_privileged,
    _require_web_session,
)


STRONG_SECRET = "widget-test-secret-that-is-long-enough-2026"


def _clear_widget_signing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("JWT_SECRET", "OISHA_API_SECRET", "OISHA_WIDGET_SECRET"):
        monkeypatch.delenv(key, raising=False)


def test_widget_signing_secret_fails_closed_without_server_secret(monkeypatch):
    _clear_widget_signing_env(monkeypatch)

    with pytest.raises(RuntimeError):
        _get_widget_jwt_secret()


def test_widget_jwt_is_bound_to_its_own_web_session(monkeypatch):
    _clear_widget_signing_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", STRONG_SECRET)

    token = issue_widget_jwt(session_id="abc123", secret=STRONG_SECRET, ttl_seconds=60)

    # Own anonymous chat is allowed.
    _require_web_session("web_abc123", authorization=f"Bearer {token}")

    # The same token must not read/write another anonymous chat.
    with pytest.raises(HTTPException) as exc_info:
        _require_web_session("web_other", authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 403


def test_widget_jwt_is_not_a_privileged_operator_credential(monkeypatch):
    _clear_widget_signing_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", STRONG_SECRET)

    token = issue_widget_jwt(session_id="abc123", secret=STRONG_SECRET, ttl_seconds=60)

    with pytest.raises(HTTPException) as exc_info:
        _require_privileged(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


def test_master_secret_can_support_legacy_operator_tools(monkeypatch):
    _clear_widget_signing_env(monkeypatch)
    monkeypatch.setenv("OISHA_API_SECRET", STRONG_SECRET)

    # Server/admin tools can still use the existing master secret while the
    # browser only receives a scoped widget JWT.
    _require_privileged(authorization=f"Bearer {STRONG_SECRET}")
    assert _get_widget_jwt_secret() == STRONG_SECRET


def test_telegram_oauth_never_uses_bot_token_as_jwt_signing_fallback():
    oauth_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "services", "api_server", "oauth.py"
    )
    with open(oauth_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    assert 'getattr(config, "JWT_SECRET", bot_token)' not in content
    assert 'or os.environ.get("OISHA_API_SECRET", "").strip()' in content
    assert "secure=True" in content
