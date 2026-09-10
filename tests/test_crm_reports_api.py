def test_sales_report_settings_defaults():
    from src.settings import settings
    assert settings.CRM_SALES_REPORT_GROUP_ID == -1003854308552
    assert settings.CRM_SALES_REPORT_TOPIC_ID == 115


import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ReportResult


@pytest.fixture
def client(monkeypatch):
    from src.api.routes import crm_reports

    class _Rep:
        def __init__(self, *a, **k):
            pass

        async def build(self, ptype):
            m = PeriodMetrics(period_type=ptype,
                              period_start=__import__("datetime").date(2026, 9, 7),
                              period_end=__import__("datetime").date(2026, 9, 7),
                              new_leads=12)
            m.recompute_derived()
            return ReportResult(ptype, m.period_start, m.period_end, m, None, {}, "BODY", True)

    monkeypatch.setattr(crm_reports, "CRMPeriodReporter", _Rep)
    monkeypatch.setattr(crm_reports, "_resolve_amocrm", lambda: object())

    app = FastAPI(title="test")
    app.include_router(crm_reports.router)
    # bypass RBAC dependency
    from src.api.rbac import Principal, Role
    app.dependency_overrides[crm_reports._principal_dep.dependency] = lambda: Principal(
        subject="t", role=Role.VIEWER, auth_type="test"
    )
    return TestClient(app)


def test_reports_endpoint_daily(client):
    r = client.get("/api/crm/reports?period=daily")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["period"] == "daily"
    assert body["metrics"]["new_leads"] == 12
    assert body["telegram_text"] == "BODY"


def test_reports_endpoint_rejects_bad_period(client):
    r = client.get("/api/crm/reports?period=hourly")
    assert r.status_code == 422


def test_reports_endpoint_unavailable_without_amocrm(client, monkeypatch):
    from src.api.routes import crm_reports
    monkeypatch.setattr(crm_reports, "_resolve_amocrm", lambda: None)
    r = client.get("/api/crm/reports?period=weekly")
    assert r.status_code == 200
    assert r.json() == {"available": False, "period": "weekly"}
