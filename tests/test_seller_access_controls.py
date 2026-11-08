"""Seller access controls: no staff PII on the public login list, PIN reset and session revocation."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.crm_access import require_dialer_access
from src.api.routes import crm_auth_routes, crm_dialer, crm_enterprise_routes
from src.services.core.crm import seller_auth
from src.services.core.crm.seller_auth import SellerAuthService

PIN = "482913"


@pytest.fixture()
def service(tmp_path, monkeypatch):
    for slug in ("BAXTIYORJON", "SHAHNOZA", "RAYXONA", "MUMTOZMAXAL", "HASANBOY"):
        monkeypatch.setenv(f"CRM_SELLER_PIN_{slug}", PIN)
    svc = SellerAuthService(db_path=str(tmp_path / "crm_dialer.db"))
    monkeypatch.setattr(seller_auth, "seller_auth_service", svc)
    monkeypatch.setattr(crm_auth_routes, "seller_auth_service", svc)
    monkeypatch.setattr("src.api.security.authorize_connection", lambda conn: None)
    return svc


@pytest.fixture()
def client(service):
    app = FastAPI()
    app.include_router(crm_auth_routes.router)
    app.include_router(crm_dialer.router)
    app.include_router(crm_enterprise_routes.router)
    return TestClient(app)


def _login(client, slug, pin=PIN):
    resp = client.post("/api/crm/dialer/auth/login", json={"slug": slug, "pin": pin})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_public_sellers_list_has_no_contact_or_role_data(client):
    sellers = client.get("/api/crm/dialer/auth/sellers").json()["sellers"]
    assert sellers and all(set(s) == {"slug", "name"} for s in sellers)


def test_public_sellers_list_is_not_a_phone_oracle(client):
    body = client.get("/api/crm/dialer/auth/sellers").text
    assert "+998" not in body and "@" not in body


def test_pin_change_logs_out_other_sessions_but_keeps_current(client):
    current = _login(client, "shahnoza")
    other = _login(client, "shahnoza")
    resp = client.post(
        "/api/crm/dialer/auth/change-pin",
        json={"old_pin": PIN, "new_pin": "735102"},
        headers={"Authorization": f"Bearer {current}"},
    )
    assert resp.status_code == 200, resp.text
    assert client.get("/api/crm/dialer/auth/me", headers={"Authorization": f"Bearer {current}"}).status_code == 200
    assert client.get("/api/crm/dialer/auth/me", headers={"Authorization": f"Bearer {other}"}).status_code == 401


def test_admin_reset_invalidates_old_pin_and_sessions(client, service):
    victim = _login(client, "rayxona")
    app = client.app
    app.dependency_overrides[require_dialer_access] = lambda: {"slug": "baxtiyorjon", "name": "Baxtiyorjon", "role": "admin"}

    resp = client.post("/api/crm/dialer/auth/admin/reset-pin", json={"slug": "rayxona"})
    assert resp.status_code == 200, resp.text
    temp = resp.json()["temp_pin"]
    assert len(temp) == 8 and temp.isdigit()
    assert resp.headers["Cache-Control"] == "no-store"

    assert client.get("/api/crm/dialer/auth/me", headers={"Authorization": f"Bearer {victim}"}).status_code == 401
    assert client.post("/api/crm/dialer/auth/login", json={"slug": "rayxona", "pin": PIN}).status_code == 401
    relogin = client.post("/api/crm/dialer/auth/login", json={"slug": "rayxona", "pin": temp})
    assert relogin.json()["pin_change_required"] is True


def test_non_admin_cannot_reset_or_list_pins(client):
    token = _login(client, "shahnoza")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/crm/dialer/auth/admin/reset-pin", json={"slug": "rayxona"}, headers=headers).status_code == 403
    assert client.get("/api/crm/dialer/auth/admin/sellers", headers=headers).status_code == 403


def test_enterprise_rbac_list_is_admin_only(client):
    token = _login(client, "shahnoza")
    assert client.get("/api/crm/dialer/rbac/users", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_sales_target_write_is_admin_only(client):
    token = _login(client, "shahnoza")
    resp = client.post(
        "/api/crm/dialer/targets",
        json={"seller_name": "x", "month_str": "2026-11", "target_revenue": 1, "target_deals": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_schema_migration_revokes_pre_existing_sessions(tmp_path, monkeypatch):
    monkeypatch.delenv("CRM_SELLER_PIN_SHAHNOZA", raising=False)
    db = str(tmp_path / "old.db")
    first = SellerAuthService(db_path=db)
    with first._get_conn() as conn:
        conn.execute("PRAGMA user_version = 0")
        conn.execute(
            "INSERT INTO crm_seller_sessions (token, seller_slug, created_at, expires_at) VALUES ('old', 'shahnoza', 0, 9999999999)"
        )
        conn.commit()
    SellerAuthService(db_path=db)
    with SellerAuthService(db_path=db)._get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM crm_seller_sessions WHERE token='old'").fetchone()[0] == 0


def test_admin_pin_status_reports_locked_and_change_required(client, service):
    client.app.dependency_overrides[require_dialer_access] = lambda: {"slug": "baxtiyorjon", "name": "B", "role": "admin"}
    with service._get_conn() as conn:
        conn.execute("UPDATE crm_seller_accounts SET pin_hash = '!locked' WHERE slug = 'hasanboy'")
        conn.commit()
    service.reset_seller_pin("rayxona")
    statuses = {s["slug"]: s["pin_status"] for s in client.get("/api/crm/dialer/auth/admin/sellers").json()["sellers"]}
    assert statuses["hasanboy"] == "locked"
    assert statuses["rayxona"] == "change_required"
    assert statuses["shahnoza"] == "active"
    listing = client.get("/api/crm/dialer/auth/admin/sellers").json()["sellers"]
    assert all("pin_hash" not in s and "phone" not in s and "tg" not in s for s in listing)


def test_directory_mode_is_declared_before_use():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "src" / "static" / "sotuv_sub.js").read_text(encoding="utf-8")
    assert 'let directoryMode = "contacts";' in js
