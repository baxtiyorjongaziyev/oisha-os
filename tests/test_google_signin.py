from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from src.api import web_auth_store as store
from src.services.api_server.core import app


@pytest.fixture
def auth(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("JWT_SECRET", "synthetic-test-secret-32-characters-long")
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "auth.db")
    return TestClient(app, base_url="https://testserver")


def test_google_page_uses_redirect_and_absolute_callback(auth):
    page = auth.get("/login")
    assert 'data-ux_mode="redirect"' in page.text
    assert 'data-login_uri="https://testserver/api/auth/google/callback"' in page.text


def test_google_callback_requires_csrf(auth, monkeypatch):
    verify = Mock(return_value=None)
    monkeypatch.setattr(store, "verify_google_credential", verify)
    response = auth.post("/api/auth/google/callback", data={"credential": "synthetic"}, follow_redirects=False)
    assert response.status_code == 400
    verify.assert_not_called()


def test_google_session_reaches_console(auth, monkeypatch):
    monkeypatch.setattr(store, "verify_google_credential", lambda _: {
        "id": 900000001, "email": "synthetic@example.test", "name": "Synthetic", "role": "targetolog",
    })
    auth.cookies.set("g_csrf_token", "synthetic-csrf")
    response = auth.post("/api/auth/google/callback", data={
        "credential": "synthetic", "g_csrf_token": "synthetic-csrf",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/api/marketing/capi/console"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert auth.get(response.headers["location"]).status_code == 200
    from unittest.mock import AsyncMock
    from src.services.core.marketing import capi_project_store
    projects = AsyncMock(return_value=[])
    monkeypatch.setattr(capi_project_store, "list_projects_for_user", projects)
    assert auth.get("/api/marketing/capi/projects").json() == []
    # Session JWT `sub` = user id (auth_service.issue_session_jwt str(user_id)),
    # authorized principal.subject is read from that claim.
    projects.assert_awaited_once_with("900000001", is_admin=False)
    auth.post("/api/auth/logout", follow_redirects=False)
    assert auth.get("/api/marketing/capi/console", follow_redirects=False).status_code == 303


def test_google_rejects_mismatched_csrf(auth, monkeypatch):
    verify = Mock()
    monkeypatch.setattr(store, "verify_google_credential", verify)
    auth.cookies.set("g_csrf_token", "synthetic-cookie")
    response = auth.post("/api/auth/google/callback", data={
        "credential": "synthetic", "g_csrf_token": "synthetic-mismatch",
    }, follow_redirects=False)
    assert response.status_code == 400
    verify.assert_not_called()


def test_google_disabled_fails_closed(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    assert store.verify_google_credential("synthetic") is None


def test_verified_google_identity_is_persistent(auth, monkeypatch):
    from google.oauth2 import id_token

    verify = Mock(return_value={
        "email_verified": True, "email": "synthetic@example.test", "name": "Synthetic",
    })
    monkeypatch.setattr(id_token, "verify_oauth2_token", verify)
    first = store.verify_google_credential("synthetic")
    assert first["id"] == store.verify_google_credential("synthetic")["id"]
    assert first["role"] == "targetolog"
    assert verify.call_args.kwargs["audience"] == "synthetic-client"
    verify.side_effect = ValueError("synthetic invalid signature")
    assert store.verify_google_credential("synthetic") is None


def test_email_registration_cannot_claim_owner(auth, monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", "synthetic-owner@example.test")
    user = store.register_or_login_email("synthetic-owner@example.test", "synthetic-password", is_register=True)
    assert user["role"] == "targetolog"
