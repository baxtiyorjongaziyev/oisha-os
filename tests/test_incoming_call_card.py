"""Tests for incoming call screen-pop card and telephony webhook."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from zoneinfo import ZoneInfo

from src.services.api_server.core import app
from src.services.call_analytics.incoming_call_card import (
    build_incoming_card,
    handle_incoming_call,
    is_incoming_call_card_enabled,
    normalize_phone,
    reset_dedup,
)

TASHKENT = ZoneInfo("Asia/Tashkent")


@pytest.fixture(autouse=True)
def clean_dedup():
    reset_dedup()
    yield
    reset_dedup()


def test_normalize_phone():
    assert normalize_phone("901234567") == "+998901234567"
    assert normalize_phone("+998901234567") == "+998901234567"
    assert normalize_phone("998901234567") == "+998901234567"
    assert normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert normalize_phone("") == ""


def test_feature_flag_disabled(monkeypatch):
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "0")
    assert not is_incoming_call_card_enabled()

    payload = {"phone": "+998901234567"}
    res = asyncio.run(handle_incoming_call(payload))
    assert not res["handled"]
    assert res["reason"] == "disabled"


def test_quiet_hours(monkeypatch):
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")
    night = datetime(2026, 10, 7, 2, 30, tzinfo=TASHKENT)

    payload = {"phone": "+998901234567"}
    res = asyncio.run(handle_incoming_call(payload, now=night))
    assert res["handled"]
    assert res["reason"] == "quiet_hours"
    assert not res["alert_sent"]


def test_deduplication(monkeypatch):
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")
    daytime = datetime(2026, 10, 7, 14, 0, tzinfo=TASHKENT)

    with patch("src.services.call_analytics.incoming_call_card._send_card", return_value=True):
        payload = {"phone": "+998901234567", "call_id": "call-101"}
        first = asyncio.run(handle_incoming_call(payload, now=daytime))
        assert first["handled"]
        assert first["alert_sent"]

        second = asyncio.run(handle_incoming_call(payload, now=daytime))
        assert not second["handled"]
        assert second["reason"] == "duplicate"


def test_client_found_in_amocrm(monkeypatch):
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")
    monkeypatch.setenv("AMOCRM_SUBDOMAIN", "jonbranding")
    daytime = datetime(2026, 10, 7, 14, 0, tzinfo=TASHKENT)

    mock_amocrm = MagicMock()
    mock_amocrm.get_contact_by_phone.return_value = {
        "id": 111,
        "name": "Ali Valiyev",
    }
    mock_amocrm.find_active_lead_by_phone.return_value = {
        "id": 999,
        "name": "Logo + Brandbook",
        "price": 15000000,
        "status_id": 87609522,  # Kvalifikatsiya
        "responsible_user_id": 55,
    }
    mock_amocrm.get_lead_notes = AsyncMock(return_value=[
        {"text": "Mijoz bilan dastlabki muloqot o'tkazildi, taklif kutilmoqda"}
    ])

    with patch("src.services.call_analytics.incoming_call_card._send_card", return_value=True) as mock_send:
        payload = {
            "phone": "+998901234567",
            "manager": "Dilshod",
            "source": "instagram",
        }
        res = asyncio.run(handle_incoming_call(payload, amocrm=mock_amocrm, now=daytime))
        assert res["handled"]
        assert res["found"]
        assert res["lead_id"] == 999
        assert res["alert_sent"]

        assert mock_send.called
        sent_text = mock_send.call_args[0][0]
        assert "+998901234567" in sent_text
        assert "Ali Valiyev" in sent_text
        assert "Logo + Brandbook" in sent_text
        assert "Kvalifikatsiya" in sent_text
        assert "15 000 000 so'm" in sent_text
        assert "Dilshod" in sent_text
        assert "instagram" in sent_text
        assert "https://jonbranding.amocrm.ru/leads/detail/999" in sent_text


def test_client_not_found_in_amocrm(monkeypatch):
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")
    daytime = datetime(2026, 10, 7, 14, 0, tzinfo=TASHKENT)

    mock_amocrm = MagicMock()
    mock_amocrm.get_contact_by_phone.return_value = None
    mock_amocrm.find_active_lead_by_phone.return_value = None

    with patch("src.services.call_analytics.incoming_call_card._send_card", return_value=True) as mock_send:
        payload = {"phone": "+998991112233"}
        res = asyncio.run(handle_incoming_call(payload, amocrm=mock_amocrm, now=daytime))
        assert res["handled"]
        assert not res["found"]
        assert res["lead_id"] is None
        assert res["alert_sent"]

        sent_text = mock_send.call_args[0][0]
        assert "Yangi raqam — CRM'da topilmadi" in sent_text


def test_amocrm_exception_handled_gracefully(monkeypatch):
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")
    daytime = datetime(2026, 10, 7, 14, 0, tzinfo=TASHKENT)

    mock_amocrm = MagicMock()
    mock_amocrm.get_contact_by_phone.side_effect = RuntimeError("AmoCRM network down")

    with patch("src.services.call_analytics.incoming_call_card._send_card", return_value=True) as mock_send:
        payload = {"phone": "+998991112233"}
        res = asyncio.run(handle_incoming_call(payload, amocrm=mock_amocrm, now=daytime))
        assert res["handled"]
        assert not res["found"]
        assert res["alert_sent"]
        assert mock_send.called


def test_route_authentication(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("TELEPHONY_WEBHOOK_SECRET", "super-secret-key-123")
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")

    payload = {"phone": "+998901234567"}

    # Noto'g'ri secret -> 401
    resp = client.post("/api/telephony/incoming-call", json=payload, headers={"X-Telephony-Secret": "wrong"})
    assert resp.status_code == 401

    # To'g'ri secret header da -> 200
    with patch("src.services.call_analytics.incoming_call_card._send_card", return_value=True):
        resp = client.post(
            "/api/telephony/incoming-call",
            json=payload,
            headers={"X-Telephony-Secret": "super-secret-key-123"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_route_bearer_and_query_secret(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("TELEPHONY_WEBHOOK_SECRET", "token-xyz")
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "1")

    payload = {"phone": "+998901234568"}

    with patch("src.services.call_analytics.incoming_call_card._send_card", return_value=True):
        # Bearer header
        resp1 = client.post(
            "/api/telephony/incoming-call",
            json=payload,
            headers={"Authorization": "Bearer token-xyz"},
        )
        assert resp1.status_code == 200

        # Query param
        payload2 = {"phone": "+998901234569"}
        resp2 = client.post(
            "/api/telephony/incoming-call?secret=token-xyz",
            json=payload2,
        )
        assert resp2.status_code == 200


def test_route_disabled_returns_disabled_status(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("INCOMING_CALL_CARD_ENABLED", "0")
    monkeypatch.delenv("TELEPHONY_WEBHOOK_SECRET", raising=False)

    payload = {"phone": "+998901234567"}
    resp = client.post("/api/telephony/incoming-call", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"
