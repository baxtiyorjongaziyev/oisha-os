"""`/api/ai/*` va `/api/erp/*` endpointlari haqiqatni aytishi kerak.

Ilgari har bir handler `except Exception: return {"error": ...}` qilib
HTTP 200 qaytarardi — buzuq endpoint monitoringda sog'lom ko'rinardi.
Endi: ishlamaydigan bog'liqlik → 503, kutilmagan xato → 500, hech qachon 200.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.ai_analytics import router as ai_router
from src.api.routes.state import api_state
from src.api.routes.erp_routes import router as erp_router

AUTH = {"Authorization": "Bearer test-secret"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "test-secret")
    # `api_state` — global; boshqa testlar unga mock qo'yib ketishi mumkin.
    # Bu yerda ataylab "hech narsa ulanmagan" holatni tekshiramiz.
    monkeypatch.setattr(api_state, "db_instance", None, raising=False)
    monkeypatch.setattr(api_state, "amocrm_instance", None, raising=False)
    app = FastAPI()
    app.include_router(ai_router)
    app.include_router(erp_router)
    return TestClient(app, raise_server_exceptions=False)


ERP_ENDPOINTS = [
    ("/api/erp/dashboard", "src.services.core.finance.erp_dashboard.ERPDashboard.get_snapshot"),
    ("/api/erp/finance", "src.services.core.finance.finance_engine.FinanceEngine.get_cash_flow_summary"),
    ("/api/erp/hr", "src.services.core.hr_engine.HREngine.get_team_summary"),
    ("/api/erp/projects", "src.services.core.project_engine.ProjectEngine.get_project_stats"),
]


@pytest.mark.parametrize("path,target", ERP_ENDPOINTS)
def test_erp_endpoints_fail_loudly(client, monkeypatch, path, target):
    """Xizmat qatlami yiqilsa — 200 + {"error": ...} emas, HTTP 500."""

    async def boom(*args, **kwargs):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(target, boom)

    response = client.get(path, headers=AUTH)

    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    # Ichki xato matni tashqariga chiqmaydi.
    assert "db exploded" not in response.text


@pytest.mark.parametrize("path,target", ERP_ENDPOINTS)
def test_erp_endpoints_reach_the_real_service(client, monkeypatch, path, target):
    """Endpoint haqiqiy metodga ulangan — nomi mos, chaqiriladi.

    Ilgari bu yerda mavjud bo'lmagan metodlar chaqirilardi
    (`get_finance_summary` va h.k.), shuning uchun hech qachon ishlamagan.
    """
    from src.services.core.finance.erp_schema import ERPSnapshot

    called = {}
    # `/dashboard` dataclass qaytaradi (route uni `asdict` qiladi), qolganlari dict.
    payload = (
        ERPSnapshot(
            period="2026-07",
            total_revenue=0,
            total_expenses=0,
            net_profit=0,
            outstanding_invoices=0,
            outstanding_amount=0,
            pending_advances=0,
            pending_advance_total=0,
            active_projects=0,
            active_employees=0,
        )
        if path.endswith("/dashboard")
        else {"ok": True}
    )

    async def spy(*args, **kwargs):
        called["yes"] = True
        return payload

    monkeypatch.setattr(target, spy)

    response = client.get(path, headers=AUTH)

    assert called.get("yes"), f"{path} haqiqiy metodni chaqirmadi"
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/api/ai/deal-hygiene", "/api/ai/metasell-dashboard"],
)
def test_ai_endpoints_report_503_when_dependency_missing(client, path):
    """AmoCRM/DB ulanmagan bo'lsa — 503, sabab ko'rsatilgan holda."""
    response = client.get(path, headers=AUTH)

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert response.json()["reason"]


def test_error_body_does_not_leak_internals(client, monkeypatch):
    """Mijozga stack/exception matni emas, umumiy xabar ketadi."""

    async def boom(*args, **kwargs):
        raise RuntimeError("SELECT * FROM secrets failed at /srv/app/db.py")

    monkeypatch.setattr(
        "src.services.core.finance.finance_engine.FinanceEngine.get_cash_flow_summary",
        boom,
    )

    body = client.get("/api/erp/finance", headers=AUTH).json()

    assert body == {"error": "internal_error", "endpoint": "erp_finance"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/ai/dashboard",
        "/api/ai/manager-ratings",
        "/api/ai/lost-clients-analysis",
        "/api/ai/skills-radar",
        "/api/ai/trend-analysis",
        "/api/ai/manager-comparison",
        "/api/ai/daily-report",
        "/api/ai/call-details/abc",
        "/api/ai/lead-classifier",
    ],
)
def test_fictional_endpoints_are_gone(client, path):
    """Hech qachon ishlamagan, xotiraga tayangan endpointlar olib tashlandi.

    Ularning o'rnini `GET /api/sales-quality/overview` bosadi.
    """
    assert client.get(path, headers=AUTH).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/ai/coach/daily-report",
        "/api/ai/coach/ideal-script",
        "/api/ai/coach/playbook-suggestions",
    ],
)
def test_coach_endpoints_report_503_without_db(client, path):
    response = client.get(path, headers=AUTH)

    assert response.status_code == 503
    assert response.json()["reason"] == "db_not_connected"


def test_erp_unauthorized_returns_401(client):
    assert client.get("/api/erp/finance").status_code == 401


def test_ai_write_endpoints_require_secret(client):
    assert client.post("/api/ai/process-call", json={}).status_code == 401
    assert client.post("/api/ai/lead-classifier/tag", json={}).status_code == 401


def test_analyze_conversation_rejects_empty_body(client):
    response = client.post("/api/ai/analyze-conversation", json={}, headers=AUTH)

    assert response.status_code == 400


def test_analyze_conversation_returns_real_scores(client):
    """Endpoint haqiqiy `QualityAnalyzer` ga ulangan."""
    response = client.post(
        "/api/ai/analyze-conversation",
        json={
            "conversation_text": (
                "Sotuvchi: Assalomu alaykum, men Jon Branding'danman.\n"
                "Mijoz: Menga brending kerak, narxi qancha?\n"
                "Sotuvchi: Loyihaga qarab. Kelishdik, ertaga taklif yuboraman.\n"
            ),
            "conversation_id": "test-1",
            "manager_name": "Sardor",
        },
        headers=AUTH,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "test-1"
    assert body["overall_score"] > 0
    assert body["scores"]


def test_process_call_requires_call_id(client):
    response = client.post("/api/ai/process-call", json={}, headers=AUTH)

    assert response.status_code == 400


def test_erp_health_reports_degraded_without_db(client):
    """Health hamon 200, lekin DB yo'qligini yashirmaydi."""
    response = client.get("/api/erp/health", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["db_connected"] is False
