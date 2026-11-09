"""Regression: /api/crm/dialer/* must not be reachable without a session."""
import secrets

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Principal, Role
from src.api.routes import crm_dialer
from src.api.security import is_protected_path

SESSION = secrets.token_urlsafe(16)
WEBHOOK = secrets.token_urlsafe(16)


def _client(monkeypatch, seller_ok=False, admin=False):
    from src.services.core.crm import seller_auth

    monkeypatch.setattr(
        seller_auth.seller_auth_service,
        "validate_session",
        lambda token: {"slug": "test"} if seller_ok and token == SESSION else None,
    )
    monkeypatch.setattr(
        "src.api.security.authorize_connection",
        lambda conn: Principal(subject="admin-test", role=Role.ADMIN, auth_type="session") if admin else None,
    )
    app = FastAPI()
    app.include_router(crm_dialer.router)
    return TestClient(app)


def test_dialer_api_rejects_anonymous(monkeypatch):
    c = _client(monkeypatch)
    for path in ("/api/crm/dialer/queue", "/api/crm/dialer/directory", "/api/crm/dialer/inbox"):
        assert c.get(path).status_code == 401, path
    assert c.post("/api/crm/dialer/inbox/send", json={}).status_code == 401


def test_dialer_api_rejects_bad_session(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/crm/dialer/catalog", headers={"X-CRM-Session-Token": SESSION + "x"})
    assert r.status_code == 401


def test_dialer_api_accepts_valid_session(monkeypatch):
    c = _client(monkeypatch, seller_ok=True)
    r = c.get("/api/crm/dialer/catalog", headers={"X-CRM-Session-Token": SESSION})
    assert r.status_code != 401


def test_dialer_api_accepts_admin_principal(monkeypatch):
    c = _client(monkeypatch, admin=True)
    assert c.get("/api/crm/dialer/catalog").status_code != 401


def test_dialer_ui_shell_and_static_stay_public(monkeypatch):
    c = _client(monkeypatch)
    for path in ("/sotuv", "/crm", "/dialer", "/static/sotuv_app.js"):
        assert c.get(path).status_code not in (401, 403), path


def test_incoming_call_webhook_secret(monkeypatch):
    monkeypatch.setenv("MOIZVONKI_WEBHOOK_SECRET", WEBHOOK)
    c = _client(monkeypatch)
    url = "/api/crm/dialer/incoming-call"
    assert c.post(url, json={}).status_code in (401, 403)
    assert c.post(url, json={}, headers={"X-Webhook-Secret": WEBHOOK + "x"}).status_code in (401, 403)
    assert c.post(url, json={}, headers={"X-Webhook-Secret": WEBHOOK}).status_code not in (401, 403)


def test_moizvonki_only_webhook_exempt_from_middleware():
    assert is_protected_path("/api/moizvonki/webhook") is False
    assert is_protected_path("/api/moizvonki/anything-else") is True
