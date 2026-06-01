import datetime
from types import SimpleNamespace

import pytest

import src.config as config
import src.services.core.amocrm_sync as amocrm_sync
import src.services.core.crm_service as crm_service
import src.services.core.enterprise_reporter as enterprise_reporter
import src.services.core.proactive_worker as proactive_worker
from src.services.core.tool_registry import ToolResult


class FakeDatabase:
    def __init__(self):
        self.marked_jobs = []

    async def is_job_run(self, job_name, run_date):
        return False

    async def mark_job_run(self, job_name, run_date):
        self.marked_jobs.append((job_name, run_date))


class FakeAmoAdapter:
    def __init__(self, leads):
        self.leads = leads
        self.task_lead_ids = []
        self.note_lead_ids = []

    async def fetch_stagnated_leads(self, hours):
        assert hours == 24
        return self.leads

    async def create_followup_task(
        self, lead_id, text, complete_till, responsible_user_id=None
    ):
        self.task_lead_ids.append(lead_id)
        return ToolResult(tool_name="amocrm", success=True)

    async def add_lead_note(self, lead_id, text):
        self.note_lead_ids.append(lead_id)
        return ToolResult(tool_name="amocrm", success=True)


class FakeRegistry:
    def __init__(self, amocrm_adapter):
        self.amocrm_adapter = amocrm_adapter

    def get(self, name):
        assert name == "amocrm_leads"
        return self.amocrm_adapter

    def list_names(self):
        return ["amocrm_leads"]


@pytest.mark.asyncio
async def test_stagnant_leads_alert_uses_current_lead():
    class FakeAmo:
        subdomain = "example"

        async def get_leads_detailed(self, limit):
            assert limit == 50
            return [
                {
                    "id": 77,
                    "name": "Lead A",
                    "status_id": 100,
                    "updated_at": 0,
                    "custom_fields_values": [
                        {"field_code": "PHONE", "values": [{"value": "+998000000000"}]}
                    ],
                }
            ]

    reporter = enterprise_reporter.EnterpriseReporter(
        db=None, crm=SimpleNamespace(amocrm=FakeAmo())
    )

    text = await reporter.get_stagnant_leads_alert()

    assert "Lead A" in text
    assert "+998000000000" in text
    assert "/leads/detail/77" in text


@pytest.mark.asyncio
async def test_conversion_push_calculates_risk_sum_and_sorts_idle_leads(monkeypatch):
    now = datetime.datetime(2026, 6, 1, 12, 5)
    now_ts = int(now.timestamp())
    leads = [
        {"id": 1, "price": 100, "updated_at": now_ts - 25 * 3600},
        {"id": 2, "price": 200, "updated_at": now_ts - 50 * 3600},
    ]
    fake_db = FakeDatabase()
    adapter = FakeAmoAdapter(leads)
    captured = {}

    class FakeAmo:
        def __init__(self, *args, **kwargs):
            pass

    class FakeCRMService:
        pass

    class FakeReporter:
        def __init__(self, db, crm):
            pass

        async def get_stagnant_leads_alert(self, limit):
            assert limit == 50
            return "stagnant leads"

    async def fake_notification_agent(db, task, executor):
        captured["task"] = task
        execution = await executor(task)
        captured["execution"] = execution
        return SimpleNamespace(success=True, verification={})

    async def fake_telegram_notification(*args, **kwargs):
        return {"success": True}

    monkeypatch.setattr(proactive_worker, "Database", lambda: fake_db)
    monkeypatch.setattr(proactive_worker, "get_local_now", lambda: now)
    monkeypatch.setattr(proactive_worker, "build_default_tool_registry", lambda **kwargs: FakeRegistry(adapter))
    monkeypatch.setattr(proactive_worker, "_run_notification_agent", fake_notification_agent)
    monkeypatch.setattr(proactive_worker, "_execute_telegram_notification", fake_telegram_notification)
    monkeypatch.setattr(amocrm_sync, "AmoCRMSync", FakeAmo)
    monkeypatch.setattr(crm_service, "CRMService", FakeCRMService)
    monkeypatch.setattr(enterprise_reporter, "EnterpriseReporter", FakeReporter)
    monkeypatch.setattr(config, "BOT_TOKEN", "fake-token", raising=False)
    monkeypatch.setattr(config, "CRM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(config, "TOPIC_CRM_ID", 52, raising=False)
    monkeypatch.setattr(config, "SALES_MANAGER_IDS", [], raising=False)

    await proactive_worker.check_amocrm_stagnation()

    assert captured["task"].payload["risk_sum"] == 300
    assert captured["execution"]["risk_sum"] == 300
    assert adapter.task_lead_ids == [2, 1]
    assert adapter.note_lead_ids == [2, 1]
    assert fake_db.marked_jobs == [("sales_conversion_push_12", "2026-06-01")]
