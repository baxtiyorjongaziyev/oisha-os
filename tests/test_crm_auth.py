"""Test CRM Seller Authentication & Session Guard."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.core.crm.seller_auth import (
    SellerAuthService,
    get_current_crm_seller,
    _hash_pin,
    _verify_pin,
)
from src.api.routes.crm_auth_routes import router as crm_auth_router


def test_pin_hashing_and_verification():
    pin = "1302"
    hashed = _hash_pin(pin)
    assert hashed != pin
    assert "$" in hashed
    assert _verify_pin("1302", hashed) is True
    assert _verify_pin("9999", hashed) is False


def test_seller_auth_service_flow(tmp_path):
    db_file = str(tmp_path / "test_auth.db")
    service = SellerAuthService(db_path=db_file)

    # List sellers
    sellers = service.list_public_sellers()
    assert len(sellers) >= 5
    for s in sellers:
        assert "pin" not in s
        assert "pin_hash" not in s

    # Authenticate with correct PIN for Shahnoza (default: 1302)
    auth = service.authenticate_seller("shahnoza", "1302")
    assert auth is not None
    assert "token" in auth
    assert auth["seller"]["slug"] == "shahnoza"

    # Authenticate with wrong PIN
    wrong_auth = service.authenticate_seller("shahnoza", "0000")
    assert wrong_auth is None

    # Validate session token
    valid = service.validate_session(auth["token"])
    assert valid is not None
    assert valid["slug"] == "shahnoza"

    # Revoke session
    revoked = service.revoke_session(auth["token"])
    assert revoked is True
    assert service.validate_session(auth["token"]) is None


def test_crm_auth_api_routes(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api_auth.db")
    test_service = SellerAuthService(db_path=db_file)
    monkeypatch.setattr("src.api.routes.crm_auth_routes.seller_auth_service", test_service)
    monkeypatch.setattr("src.services.core.crm.seller_auth.seller_auth_service", test_service)

    app = FastAPI()
    app.include_router(crm_auth_router)
    client = TestClient(app)

    # 1. Get sellers
    r = client.get("/api/crm/dialer/auth/sellers")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert len(data["sellers"]) >= 5

    # 2. Login with wrong PIN
    r = client.post("/api/crm/dialer/auth/login", json={"slug": "shahnoza", "pin": "9999"})
    assert r.status_code == 401

    # 3. Login with correct PIN
    r = client.post("/api/crm/dialer/auth/login", json={"slug": "shahnoza", "pin": "1302"})
    assert r.status_code == 200
    res_data = r.json()
    assert res_data["success"] is True
    token = res_data["token"]
    assert token

    # 4. Check protected endpoint with token header
    r = client.get("/api/crm/dialer/auth/me", headers={"X-CRM-Session-Token": token})
    assert r.status_code == 200
    assert r.json()["seller"]["slug"] == "shahnoza"

    # 5. Check protected endpoint without token
    r = client.get("/api/crm/dialer/auth/me")
    assert r.status_code == 401
