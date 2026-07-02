import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.callmaster_routes import router
from src.services.core.callmaster_service import normalize_phone


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("CALLMASTER_STATE_FILE", str(tmp_path / "callmaster.json"))
    monkeypatch.setenv("CALLMASTER_API_SECRET", "admin-secret")
    monkeypatch.setenv("CALLMASTER_WEBHOOK_SECRET", "webhook-secret")
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _admin_headers():
    return {"Authorization": "Bearer admin-secret"}


def _signed_headers(raw_body: bytes):
    digest = hmac.new(b"webhook-secret", raw_body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Callmaster-Signature": f"sha256={digest}",
    }


def test_normalize_phone_accepts_uzbek_formats():
    assert normalize_phone("+998 90 123 45 67") == "+998901234567"
    assert normalize_phone("90 123 45 67") == "+998901234567"
    assert normalize_phone("0901234567") == "+998901234567"


def test_campaign_contact_launch_and_pressed_one_webhook(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    created = client.post(
        "/api/callmaster/campaigns",
        headers=_admin_headers(),
        json={
            "name": "Brif eslatma",
            "audio_url": "https://example.test/audio/brif.wav",
            "max_parallel_calls": 25,
        },
    )
    assert created.status_code == 200
    campaign_id = created.json()["campaign"]["id"]

    imported = client.post(
        f"/api/callmaster/campaigns/{campaign_id}/contacts",
        headers=_admin_headers(),
        json={
            "contacts": [
                {"phone": "+998 90 123 45 67", "name": "Ali", "lead_id": 101},
                {"phone": "901234567", "name": "Duplicate"},
                {"phone": "abc"},
            ]
        },
    )
    payload = imported.json()
    assert imported.status_code == 200
    assert len(payload["created"]) == 1
    assert len(payload["skipped"]) == 2
    contact_id = payload["created"][0]["id"]

    launched = client.post(
        f"/api/callmaster/campaigns/{campaign_id}/launch",
        headers=_admin_headers(),
        json={"provider": "local"},
    )
    assert launched.status_code == 200
    attempts = launched.json()["queued_attempts"]
    assert len(attempts) == 1
    attempt_id = attempts[0]["id"]

    webhook_body = {
        "campaign_id": campaign_id,
        "contact_id": contact_id,
        "attempt_id": attempt_id,
        "event": "answered",
        "digit": "1",
        "duration_sec": 17,
    }
    raw_body = json.dumps(webhook_body).encode("utf-8")
    webhook = client.post(
        "/api/callmaster/webhook",
        headers=_signed_headers(raw_body),
        content=raw_body,
    )
    assert webhook.status_code == 200
    result = webhook.json()
    assert result["contact"]["status"] == "pressed_1"
    assert result["attempt"]["duration_sec"] == 17
    assert result["action"]["type"] == "operator_handoff"
    assert result["action"]["amocrm"]["lead_id"] == 101

    summary = client.get(
        f"/api/callmaster/campaigns/{campaign_id}",
        headers=_admin_headers(),
    ).json()["summary"]
    assert summary["contacts_total"] == 1
    assert summary["pressed_1"] == 1


def test_admin_secret_required(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/api/callmaster/campaigns",
        json={"name": "No auth", "audio_url": "https://example.test/a.wav"},
    )

    assert response.status_code == 401


def test_webhook_rejects_bad_signature(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/api/callmaster/webhook",
        headers={"X-Callmaster-Signature": "sha256=bad"},
        json={"event": "answered"},
    )

    assert response.status_code == 401

