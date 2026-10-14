"""Tests for Targetolog self-service access and CAPI automation."""
import time
import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Permission, Role, has_permission, Principal
from src.api.routes.capi_platform import router
from src.api.security import ApiAccessMiddleware
from src.services.core.dispatcher.handlers_capi import format_capi_status_text, build_capi_keyboard
from src.schedulers.leadgen_status_reporter import _capi_telemetry_lines

SECRET = "synthetic-targetolog-test-secret-at-least-32bytes"


def _token(role: str, subject: str = "targetolog-1") -> dict[str, str]:
    return {
        "oisha_token": jwt.encode(
            {"sub": subject, "role": role, "exp": int(time.time()) + 60},
            SECRET,
            algorithm="HS256",
        )
    }


def _app(monkeypatch) -> TestClient:
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.delenv("OISHA_API_SECRET", raising=False)
    app = FastAPI()
    app.add_middleware(ApiAccessMiddleware)
    app.include_router(router)
    return TestClient(app)


def test_targetolog_role_permissions():
    targetolog = Principal(subject="target-1", role=Role.TARGETOLOG, auth_type="bearer")
    assert has_permission(targetolog, Permission.MARKETING_READ)
    assert has_permission(targetolog, Permission.MARKETING_MANAGE)
    assert has_permission(targetolog, Permission.DASHBOARD_READ)
    assert not has_permission(targetolog, Permission.SYSTEM_DEPLOY)

    admin = Principal(subject="admin-1", role=Role.ADMIN, auth_type="bearer")
    assert has_permission(admin, Permission.MARKETING_READ)
    assert has_permission(admin, Permission.MARKETING_MANAGE)


def test_targetolog_can_access_summary(monkeypatch):
    client = _app(monkeypatch)
    # Seller cannot access CAPI summary
    seller_res = client.get("/api/marketing/capi/summary", cookies=_token("seller"))
    assert seller_res.status_code == 403

    # Targetolog can access CAPI summary
    targetolog_res = client.get("/api/marketing/capi/summary", cookies=_token("targetolog"))
    assert targetolog_res.status_code == 200
    data = targetolog_res.json()
    assert "configuration" in data
    assert "total_website_events" in data
    assert "website_status_counts" in data


def test_targetolog_can_access_console(monkeypatch):
    client = _app(monkeypatch)
    # Unauthenticated browser redirects to telegram login
    unauth = client.get(
        "/api/marketing/capi/console",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert unauth.status_code == 303
    assert "/api/auth/telegram/login" in unauth.headers["location"]

    # Seller is forbidden (403)
    seller_res = client.get("/api/marketing/capi/console", cookies=_token("seller"))
    assert seller_res.status_code == 403

    # Targetolog gets 200 console
    res = client.get("/api/marketing/capi/console", cookies=_token("targetolog"))
    assert res.status_code == 200
    assert "Targetolog CAPI Paneli" in res.text


def test_targetolog_can_dispatch_queue(monkeypatch):
    client = _app(monkeypatch)
    # Origin required for cookie mutation
    res_no_origin = client.post("/api/marketing/capi/dispatch", cookies=_token("targetolog"))
    assert res_no_origin.status_code == 403

    # With origin
    res = client.post(
        "/api/marketing/capi/dispatch",
        cookies=_token("targetolog"),
        headers={"Origin": "http://testserver"},
    )
    assert res.status_code == 200
    assert "results" in res.json()


def test_format_capi_status_text():
    mock_snapshot = {
        "configuration": {
            "configured": True,
            "dataset_id": "1134785364752294",
            "mode": "test",
            "enabled": True,
            "ingest_configured": True,
        },
        "events": [
            {"event_name": "Lead", "status": "sent"},
            {"event_name": "PageView", "status": "sent"},
        ],
        "crm_events": [
            {"event_name": "QualifiedLead", "status": "sent"},
            {"event_name": "Purchase", "status": "sent"},
        ],
    }
    text = format_capi_status_text(mock_snapshot)
    assert "TARGETOLOG PANELI" in text
    assert "1134785364752294" in text
    assert "Lead" in text
    assert "Purchase" in text
    assert "Meta qabul qilgan (Sent)" in text


def test_build_capi_keyboard():
    kb = build_capi_keyboard()
    assert kb is not None
    assert len(kb.inline_keyboard) == 2
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    assert "capi:dispatch" in callbacks
    assert "capi:events" in callbacks


def test_capi_telemetry_lines(monkeypatch):
    from src.settings import settings
    monkeypatch.setattr(settings, "META_CAPI_DATASET_ID", "1134785364752294")
    monkeypatch.setattr(settings, "META_CAPI_ENABLED", True)
    lines = _capi_telemetry_lines()
    assert len(lines) == 2
    assert "1134785364752294" in lines[0]
