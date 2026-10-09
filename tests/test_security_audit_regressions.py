"""Regressions for the vibe-security audit findings (webhooks, OpenClaw, CORS)."""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.security import is_protected_path


def _notes_app():
    from src.services.api_server import webhooks

    app = FastAPI()
    app.state.limiter = webhooks.limiter
    app.include_router(webhooks.router)
    return app


_TG_NOTE = {
    "notes[add][0][text]": "TG: phishing link",
    "notes[add][0][element_id]": "777",
}


def test_amocrm_notes_webhook_rejects_missing_token():
    from src.api.routes import amocrm_integration

    with patch.object(amocrm_integration, "_amocrm_webhook_secret_configured", return_value="s3cret"), \
         patch("src.services.core.crm.amocrm_sync.AmoCRMSync") as sync:
        client = TestClient(_notes_app())
        missing = client.post("/webhook/amocrm_notes", data=_TG_NOTE)
        wrong = client.post("/webhook/amocrm_notes?token=nope", data=_TG_NOTE)
    assert missing.status_code == 401
    assert wrong.status_code == 401
    sync.assert_not_called()


def test_amocrm_notes_webhook_accepts_valid_token():
    from src.api.routes import amocrm_integration
    from src.services.api_server import webhooks

    with patch.object(amocrm_integration, "_amocrm_webhook_secret_configured", return_value="s3cret"), \
         patch.object(webhooks, "_get_amocrm_instance", return_value=None), \
         patch.object(webhooks, "_get_db_instance", AsyncMock(return_value=None)):
        resp = TestClient(_notes_app()).post(
            "/webhook/amocrm_notes?token=s3cret", data={"notes[add][0][text]": "hi"}
        )
    assert resp.json() == {"status": "ok"}


def _openclaw_client():
    from src.api.routes.openclaw_gateway import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_openclaw_webhook_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("OPENCLAW_SECRET", raising=False)
    with patch("src.openclaw_bridge.handle_openclaw_message") as handler:
        resp = _openclaw_client().post("/webhook/openclaw", json={"message": "hi"})
    assert resp.status_code == 503
    handler.assert_not_called()


def test_openclaw_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SECRET", "k")
    resp = _openclaw_client().post(
        "/webhook/openclaw",
        content=json.dumps({"message": "hi"}),
        headers={"x-openclaw-signature": "bad"},
    )
    assert resp.status_code == 403


def test_openclaw_webhook_signature_is_checked_against_body(monkeypatch):
    monkeypatch.setenv("OPENCLAW_SECRET", "k")
    body = json.dumps({"message": "hi"}).encode()
    sig = hmac.new(b"k", body, hashlib.sha256).hexdigest()
    resp = _openclaw_client().post(
        "/webhook/openclaw", content=body, headers={"x-openclaw-signature": sig}
    )
    assert resp.status_code != 403


def test_openai_compatible_gateway_is_protected():
    assert is_protected_path("/v1/chat/completions")
    assert is_protected_path("/v1/models")


def test_cors_does_not_reflect_origin_with_credentials():
    from src.api_server import app

    resp = TestClient(app).get(
        "/healthz", headers={"Origin": "https://evil.example", "Cookie": "oisha_token=x"}
    )
    assert resp.headers.get("access-control-allow-origin") == "*"
    assert resp.headers.get("access-control-allow-credentials") is None
