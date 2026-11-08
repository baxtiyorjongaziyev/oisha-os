"""Seller PIN hardening and remaining dialer-namespace guards (audit 2026-11-07).

tests/test_crm_dialer_auth.py covers the crm_dialer router guard. This file
covers what sits around it: the enterprise router, FastAPI schema/docs, PIN
seeding, brute-force lockout, forced change of weak PINs and login-by-phone.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import crm_auth_routes, crm_dialer, crm_enterprise_routes
from src.services.core.crm import seller_auth
from src.services.core.crm.seller_auth import (
    INITIAL_SELLERS,
    MAX_FAILED_LOGINS,
    SellerAuthService,
)

PIN = "482913"
WEAK = "9001"
STRONG = "735102"


class _NoRing:
    def get_active_ring(self, rep_slug: str):
        return None


@pytest.fixture()
def auth_service(tmp_path, monkeypatch):
    for s in INITIAL_SELLERS:
        monkeypatch.delenv(f"CRM_SELLER_PIN_{s['slug'].upper()}", raising=False)
    monkeypatch.setenv("CRM_SELLER_PIN_SHAHNOZA", PIN)
    service = SellerAuthService(db_path=str(tmp_path / "crm_dialer.db"))
    monkeypatch.setattr(seller_auth, "seller_auth_service", service)
    monkeypatch.setattr(crm_auth_routes, "seller_auth_service", service)
    monkeypatch.setattr("src.api.security.authorize_connection", lambda conn: None)
    return service


@pytest.fixture()
def client(auth_service, monkeypatch):
    monkeypatch.setattr(crm_dialer, "caller_id_hub", _NoRing())
    app = FastAPI()
    app.include_router(crm_dialer.router)
    app.include_router(crm_auth_routes.router)
    app.include_router(crm_enterprise_routes.router)
    return TestClient(app)


def _login(client, slug="shahnoza", pin=PIN) -> dict:
    resp = client.post("/api/crm/dialer/auth/login", json={"slug": slug, "pin": pin})
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- enterprise router + schema --------------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/crm/dialer/rbac/users"),
        ("GET", "/api/crm/dialer/loss-analytics"),
        ("POST", "/api/crm/dialer/targets"),
        ("POST", "/api/crm/dialer/lead/1/loss"),
        ("POST", "/api/crm/dialer/digital-pipeline/trigger"),
    ],
)
def test_enterprise_routes_reject_anonymous(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_every_enterprise_route_has_the_dialer_guard():
    for route in crm_enterprise_routes.router.routes:
        calls = {dep.call for dep in route.dependant.dependencies}
        assert crm_dialer.require_dialer_access in calls, route.path


def test_full_app_protects_dialer_api_and_schema():
    from src.api_server import app

    api = TestClient(app, base_url="https://oisha.example")
    for path in ("/api/crm/dialer/catalog", "/api/crm/dialer/rbac/users", "/openapi.json", "/docs", "/redoc"):
        assert api.get(path).status_code == 401, path


# --- PIN seeding -----------------------------------------------------------

def test_seed_has_no_plaintext_default_pins():
    assert all("default_pin" not in s for s in INITIAL_SELLERS)


def test_fresh_db_without_env_pin_keeps_account_locked(auth_service):
    for pin in ("8128", "0000", PIN):
        assert auth_service.authenticate_seller("baxtiyorjon", pin) is None


def test_env_pin_unlocks_account_seeded_while_locked(tmp_path, monkeypatch):
    db_path = str(tmp_path / "crm_dialer.db")
    monkeypatch.delenv("CRM_SELLER_PIN_RAYXONA", raising=False)
    SellerAuthService(db_path=db_path)
    monkeypatch.setenv("CRM_SELLER_PIN_RAYXONA", STRONG)
    result = SellerAuthService(db_path=db_path).authenticate_seller("rayxona", STRONG)
    assert result and result["seller"]["slug"] == "rayxona"


# --- brute-force lockout ---------------------------------------------------

def test_repeated_wrong_pins_lock_the_seller(auth_service):
    for _ in range(MAX_FAILED_LOGINS):
        assert auth_service.authenticate_seller("shahnoza", "000000") is None
    assert auth_service.login_retry_after("shahnoza") > 0
    assert auth_service.authenticate_seller("shahnoza", PIN) is None  # even the right PIN


def test_successful_login_resets_failure_count(auth_service):
    for _ in range(MAX_FAILED_LOGINS - 1):
        auth_service.authenticate_seller("shahnoza", "000000")
    assert auth_service.authenticate_seller("shahnoza", PIN) is not None
    for _ in range(MAX_FAILED_LOGINS - 1):
        auth_service.authenticate_seller("shahnoza", "000000")
    assert auth_service.login_retry_after("shahnoza") == 0


def test_login_route_returns_429_with_retry_after_when_locked(client):
    for _ in range(MAX_FAILED_LOGINS):
        resp = client.post("/api/crm/dialer/auth/login", json={"slug": "shahnoza", "pin": "000000"})
        assert resp.status_code == 401
    resp = client.post("/api/crm/dialer/auth/login", json={"slug": "shahnoza", "pin": PIN})
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


# --- login by phone --------------------------------------------------------

def test_login_by_phone_never_matches_seller_with_blank_phone(client, auth_service):
    # baxtiyorjon sorts first by rep_id; endswith("") used to match him for any number.
    with auth_service._get_conn() as conn:
        conn.execute("UPDATE crm_seller_accounts SET phone = '' WHERE slug = 'baxtiyorjon'")
        conn.commit()
    resp = client.post("/api/crm/dialer/auth/login-by-phone", json={"phone": "+998901112233", "pin": PIN})
    # Same answer as a wrong PIN: no account enumeration by phone.
    assert resp.status_code == 401


def test_login_by_phone_matches_national_number(client):
    resp = client.post("/api/crm/dialer/auth/login-by-phone", json={"phone": "77 322 00 42", "pin": PIN})
    assert resp.status_code == 200
    assert resp.json()["seller"]["slug"] == "shahnoza"


# --- weak PIN: session limited to /me, /change-pin, /logout ----------------

@pytest.fixture()
def weak_client(client, auth_service, monkeypatch):
    monkeypatch.setenv("CRM_SELLER_PIN_RAYXONA", WEAK)
    SellerAuthService(db_path=auth_service.db_path)  # re-seed: unlocks rayxona with the 4-digit PIN
    return client


def _weak_headers(client) -> dict:
    data = _login(client, "rayxona", WEAK)
    assert data["pin_change_required"] is True
    return {"Authorization": f"Bearer {data['token']}"}


def test_strong_pin_login_needs_no_change(client):
    assert _login(client)["pin_change_required"] is False


def test_strong_pin_session_reaches_data_routes(client):
    headers = {"Authorization": f"Bearer {_login(client)['token']}"}
    assert client.get("/api/crm/dialer/caller-id/active", headers=headers).status_code == 200


def test_weak_pin_session_is_blocked_from_data_routes(weak_client):
    headers = _weak_headers(weak_client)
    resp = weak_client.get("/api/crm/dialer/caller-id/active", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "pin_change_required"
    me = weak_client.get("/api/crm/dialer/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["pin_change_required"] is True


def test_changing_weak_pin_unlocks_the_session(weak_client):
    headers = _weak_headers(weak_client)
    resp = weak_client.post(
        "/api/crm/dialer/auth/change-pin", json={"old_pin": WEAK, "new_pin": STRONG}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert weak_client.get("/api/crm/dialer/caller-id/active", headers=headers).status_code == 200
    assert _login(weak_client, "rayxona", STRONG)["pin_change_required"] is False


@pytest.mark.parametrize("new_pin,expected", [("12345", 422), ("900100", 200)])
def test_change_pin_enforces_minimum_length(weak_client, new_pin, expected):
    resp = weak_client.post(
        "/api/crm/dialer/auth/change-pin",
        json={"old_pin": WEAK, "new_pin": new_pin},
        headers=_weak_headers(weak_client),
    )
    assert resp.status_code == expected


def test_change_pin_rejects_wrong_old_pin(weak_client):
    resp = weak_client.post(
        "/api/crm/dialer/auth/change-pin",
        json={"old_pin": "0000", "new_pin": STRONG},
        headers=_weak_headers(weak_client),
    )
    assert resp.status_code == 400
