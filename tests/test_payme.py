"""Tests for Payme Merchant API endpoint."""
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.services.api_server.core import app
from src.api.routes.state import api_state

TEST_KEY = "test_payme_secret_key"


@pytest.fixture
def auth_header():
    token = base64.b64encode(f"Paycom:{TEST_KEY}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("PAYME_KEY", TEST_KEY)
    monkeypatch.setenv("PAYME_ENABLED", "true")


def test_payme_disabled(monkeypatch, auth_header):
    monkeypatch.setenv("PAYME_ENABLED", "false")
    client = TestClient(app)
    resp = client.post("/payme", json={"id": 1, "method": "CheckPerformTransaction"}, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"]["code"] == -31008


def test_payme_unauthorized():
    client = TestClient(app)
    resp = client.post("/payme", json={"id": 1, "method": "CheckPerformTransaction"}, headers={"Authorization": "Basic invalid"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"]["code"] == -32504


def test_payme_missing_invoice(auth_header):
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=[])
    with patch.object(api_state, "db_instance", mock_db):
        client = TestClient(app)
        resp = client.post(
            "/payme",
            json={"id": 2, "method": "CheckPerformTransaction", "params": {"account": {"invoice_id": "999"}}},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"]["code"] == -31050


def test_payme_invalid_amount(auth_header):
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=[{"id": 10, "amount": 50000, "paid_amount": 0, "status": "pending"}])
    with patch.object(api_state, "db_instance", mock_db):
        client = TestClient(app)
        resp = client.post(
            "/payme",
            json={"id": 3, "method": "CheckPerformTransaction", "params": {"account": {"invoice_id": "10"}, "amount": 100000}},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"]["code"] == -31001


def test_payme_check_perform_success(auth_header):
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=[{"id": 10, "amount": 50000, "paid_amount": 0, "status": "pending"}])
    with patch.object(api_state, "db_instance", mock_db):
        client = TestClient(app)
        resp = client.post(
            "/payme",
            json={"id": 4, "method": "CheckPerformTransaction", "params": {"account": {"invoice_id": "10"}, "amount": 5000000}},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["allow"] is True


def test_payme_perform_transaction(auth_header):
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=[{"id": 10, "amount": 50000, "paid_amount": 0, "status": "pending"}])
    mock_db.commit = AsyncMock()
    with patch.object(api_state, "db_instance", mock_db):
        client = TestClient(app)
        resp = client.post(
            "/api/payme",
            json={"id": 5, "method": "PerformTransaction", "params": {"account": {"invoice_id": "10"}, "amount": 5000000}},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["state"] == 2
        mock_db.commit.assert_awaited_once()
