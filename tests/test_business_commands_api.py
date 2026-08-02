from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.business_commands import router
from src.api.routes.state import api_state


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_business_command_routes_require_auth(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)

    response = _client().get("/api/oisha/telegram/migration")

    assert response.status_code == 401


def test_telegram_migration_endpoint_is_read_only_and_secret_safe(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setenv("USERBOT_RUNTIME_OWNER", "oracle_vm")
    monkeypatch.setenv("USERBOT_SESSION_STRING", "secret-session")
    monkeypatch.setenv("BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_BOT_RUNTIME_BACKEND", "aiogram")

    response = _client().get(
        "/api/oisha/telegram/migration",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()
    serialized = repr(body)

    assert response.status_code == 200
    assert body["status"]["stage"] == "aiogram_send_only"
    assert body["status"]["rollback_backend"] == "telethon"
    assert "secret-session" not in serialized
    assert "secret-token" not in serialized


def test_erp_roadmap_endpoint_keeps_integration_first_policy(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)

    response = _client().get(
        "/api/oisha/erp/roadmap",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert "Integration ERP Brain" in body["positioning"]
    assert any("external" in principle for principle in body["principles"])
    assert any(phase["title"] == "Aiogram bot head migration" for phase in body["phases"])


def test_sales_today_priorities_returns_source_unavailable_without_crm(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr(api_state, "amocrm_instance", None)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_amocrm", lambda: None)

    response = _client().get(
        "/api/oisha/sales/today-priorities",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "source_unavailable"
    assert body["items"] == []
    assert "No fake priorities" in body["claim_policy"]


def test_sales_today_priorities_reads_amocrm_and_ranks(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    fake_amocrm = _FakeAmoCRM()
    monkeypatch.setattr(api_state, "amocrm_instance", fake_amocrm)

    response = _client().get(
        "/api/oisha/sales/today-priorities?limit=2",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["items"][0]["lead_id"] == 11
    assert "no_open_task" in body["items"][0]["reasons"]
    assert fake_amocrm.requested_limit >= 20
    assert fake_amocrm.task_checks == [11, 12]


def test_project_risks_returns_source_unavailable_without_airtable(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_airtable", lambda: None)

    response = _client().get(
        "/api/oisha/projects/risks",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "source_unavailable"
    assert body["items"] == []
    assert "No fake project risks" in body["claim_policy"]


def test_project_risks_reads_airtable_and_ranks(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr(
        "src.api.routes.business_commands._get_runtime_airtable",
        lambda: _FakeAirtable(),
    )

    response = _client().get(
        "/api/oisha/projects/risks?limit=2",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["items"][0]["project_id"] == "rec1"
    assert "deadline_missing" in body["items"][0]["reasons"]


def test_finance_risks_returns_source_unavailable_without_source(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_airtable", lambda: None)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_project_engine", lambda: None)

    response = _client().get(
        "/api/oisha/finance/risks",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "source_unavailable"
    assert "No fake finance risks" in body["claim_policy"]


def test_finance_risks_reads_airtable_and_keeps_margin_unguessed(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr(
        "src.api.routes.business_commands._get_runtime_airtable",
        lambda: _FakeFinanceAirtable(),
    )

    response = _client().get(
        "/api/oisha/finance/risks?limit=2",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["items"][0]["project_id"] == "fin1"
    assert "advance_below_50" in body["items"][0]["reasons"]
    assert body["items"][0]["evidence"]["margin"] is None


def test_team_capacity_returns_source_unavailable_without_source(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_airtable", lambda: None)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_project_engine", lambda: None)
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_hr_engine", lambda: None)

    response = _client().get(
        "/api/oisha/team/capacity",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "source_unavailable"
    assert "No fake team capacity" in body["claim_policy"]


def test_team_capacity_reads_airtable_and_ranks(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    monkeypatch.setattr(
        "src.api.routes.business_commands._get_runtime_airtable",
        lambda: _FakeTeamAirtable(),
    )
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_hr_engine", lambda: None)

    response = _client().get(
        "/api/oisha/team/capacity?limit=2",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    ali = next(item for item in body["items"] if item["owner_name"] == "Ali")
    assert "overdue_projects" in ali["reasons"]
    assert body["unassigned_project_count"] == 1


def test_command_center_aggregates_sections_without_fake_fill(monkeypatch):
    monkeypatch.setenv("OISHA_API_SECRET", "api-secret")
    from src.settings import settings
    monkeypatch.setattr(settings, "OISHA_API_SECRET", "api-secret", raising=False)
    fake_amocrm = _FakeAmoCRM()
    monkeypatch.setattr(api_state, "amocrm_instance", fake_amocrm)
    monkeypatch.setattr(
        "src.api.routes.business_commands._get_runtime_airtable",
        lambda: _FakeCommandCenterAirtable(),
    )
    monkeypatch.setattr("src.api.routes.business_commands._get_runtime_hr_engine", lambda: None)

    response = _client().get(
        "/api/oisha/command-center?limit=2",
        headers={"Authorization": "Bearer api-secret"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] in {"attention_required", "partial"}
    assert set(body["sections"]) == {"sales", "projects", "finance", "team"}
    assert body["summary"]["total_sections"] == 4
    assert "guesses" in body["claim_policy"]


class _FakeAmoCRM:
    last_error = None

    def __init__(self):
        self.requested_limit = 0
        self.task_checks = []

    async def get_leads_detailed(self, limit: int = 50):
        self.requested_limit = limit
        return [
            {
                "id": 11,
                "name": "Hot lead",
                "status_id": 801,
                "responsible_user_id": None,
                "price": 25_000_000,
                "updated_at": 1,
                "_embedded": {"contacts": [{"id": 1}]},
            },
            {
                "id": 12,
                "name": "Warm lead",
                "status_id": 802,
                "responsible_user_id": 5,
                "price": 1_000_000,
                "updated_at": 1,
                "_embedded": {"contacts": [{"id": 2}]},
            },
        ]

    async def get_lead_open_tasks(self, lead_id: int):
        self.task_checks.append(lead_id)
        if lead_id == 12:
            return [{"complete_till": 4_102_444_800}]
        return []


class _FakeAirtable:
    def get_projects(self):
        return [
            {
                "id": "rec1",
                "fields": {
                    "Project Name": "No deadline",
                    "Stage": "Design",
                    "Manager": "",
                },
            },
            {
                "id": "rec2",
                "fields": {
                    "Project Name": "Done",
                    "Stage": "Completed",
                    "Deadline": "2026-07-01",
                    "Manager": "Ali",
                },
            },
        ]


class _FakeFinanceAirtable:
    def get_projects(self):
        return [
            {
                "id": "fin1",
                "fields": {
                    "Project Name": "Brandbook",
                    "Stage": "Design",
                    "Budget": "20 000 000",
                    "To'langan": "2 000 000",
                    "To'lov statusi": "partial",
                },
            }
        ]


class _FakeTeamAirtable:
    def get_projects(self):
        return [
            {
                "id": "team1",
                "fields": {
                    "Project Name": "Brandbook",
                    "Stage": "Design",
                    "Manager": "Ali",
                    "Deadline": "2026-01-01",
                },
            },
            {
                "id": "team2",
                "fields": {
                    "Project Name": "Landing",
                    "Stage": "",
                    "Manager": "",
                },
            },
        ]


class _FakeCommandCenterAirtable:
    def get_projects(self):
        return [
            {
                "id": "cc1",
                "fields": {
                    "Project Name": "Command project",
                    "Stage": "Design",
                    "Manager": "Ali",
                    "Deadline": "2026-01-01",
                    "Budget": "10 000 000",
                    "To'langan": "2 000 000",
                },
            }
        ]
