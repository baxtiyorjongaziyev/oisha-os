import time
from types import SimpleNamespace

import pytest

from src import api_server


class FakeStateDB:
    def __init__(self):
        self.state = {}
        self.connection = None

    async def get_state(self, key, default=None):
        return self.state.get(key, default)

    async def set_state(self, key, value):
        self.state[key] = value
        return True

    async def get_connection(self):
        return self.connection


class FakeTotalsCursor:
    async def fetchone(self):
        return {
            "total_analyses": 3,
            "amocrm_analyses": 2,
            "tasks_created": 1,
            "latest_analyzed_at": "2026-05-25T10:00:00+00:00",
        }


class FakeTotalsConnection:
    def execute(self, *_args, **_kwargs):
        return FakeTotalsCursor()


@pytest.mark.asyncio
async def test_call_backfill_scheduler_queues_and_records_start(monkeypatch):
    db = FakeStateDB()
    calls = []

    async def fake_run(runtime_db, *, reason, limit=None):
        calls.append((runtime_db, reason, limit))
        return {"ok": True, "leads_scanned": 2, "calls_processed": 1}

    monkeypatch.setattr(api_server.settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True, raising=False)
    monkeypatch.setattr(api_server.settings, "AMOCRM_CALL_BACKFILL_ON_WEBHOOK", True, raising=False)
    monkeypatch.setattr(api_server, "_run_amocrm_call_backfill", fake_run)
    monkeypatch.setattr(api_server, "_call_backfill_task", None, raising=False)

    result = await api_server._schedule_amocrm_call_backfill(
        db,
        reason="test",
        limit=7,
        force=True,
    )

    assert result == {"queued": True, "reason": "test", "limit": 7}
    assert api_server._CALL_BACKFILL_LAST_STARTED_KEY in db.state

    task = api_server._call_backfill_task
    assert task is not None
    await task
    assert calls == [(db, "test", 7)]
    api_server._call_backfill_task = None


@pytest.mark.asyncio
async def test_call_backfill_scheduler_throttles_recent_run(monkeypatch):
    db = FakeStateDB()
    db.state[api_server._CALL_BACKFILL_LAST_STARTED_KEY] = str(time.time())

    monkeypatch.setattr(api_server.settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True, raising=False)
    monkeypatch.setattr(api_server.settings, "AMOCRM_CALL_BACKFILL_ON_WEBHOOK", True, raising=False)
    monkeypatch.setattr(
        api_server.settings,
        "AMOCRM_CALL_BACKFILL_INTERVAL_MINUTES",
        60,
        raising=False,
    )
    monkeypatch.setattr(api_server, "_call_backfill_task", None, raising=False)

    result = await api_server._schedule_amocrm_call_backfill(
        db,
        reason="test",
        force=False,
    )

    assert result["queued"] is False
    assert result["reason"] == "throttled"
    assert result["retry_after_seconds"] > 0


def test_cron_request_accepts_oisha_api_secret(monkeypatch):
    monkeypatch.setattr(api_server.settings, "AMOCRM_CRON_SECRET", None, raising=False)
    monkeypatch.setenv("OISHA_API_SECRET", "secret-123")

    request = SimpleNamespace(headers={"Authorization": "Bearer secret-123"})

    assert api_server._is_authorized_cron_request(request) is True


def test_cron_request_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(api_server.settings, "AMOCRM_CRON_SECRET", None, raising=False)
    monkeypatch.setenv("OISHA_API_SECRET", "secret-123")

    request = SimpleNamespace(headers={"Authorization": "Bearer wrong"})

    assert api_server._is_authorized_cron_request(request) is False


@pytest.mark.asyncio
async def test_call_analysis_status_reports_last_run_and_totals(monkeypatch):
    db = FakeStateDB()
    db.connection = FakeTotalsConnection()
    db.state[api_server._CALL_BACKFILL_LAST_STARTED_KEY] = "1779690000"
    db.state[api_server._CALL_BACKFILL_LAST_FINISHED_KEY] = "1779690060"
    db.state[api_server._CALL_BACKFILL_LAST_RESULT_KEY] = (
        '{"ok": true, "leads_scanned": 20, "calls_processed": 1}'
    )
    monkeypatch.setattr(api_server, "_call_backfill_task", None, raising=False)
    monkeypatch.setattr(api_server.settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True, raising=False)
    monkeypatch.setattr(api_server.settings, "AMOCRM_CALL_BACKFILL_LIMIT", 50, raising=False)
    monkeypatch.setattr(api_server.settings, "ENABLE_AMOCRM_CALL_TASKS", True, raising=False)

    status = await api_server._build_amocrm_call_analysis_status(db)

    assert status["ok"] is True
    assert status["running"] is False
    assert status["last_run"]["result"]["calls_processed"] == 1
    assert status["totals"]["total_analyses"] == 3
    assert status["totals"]["tasks_created"] == 1


@pytest.mark.asyncio
async def test_call_analysis_status_uses_memory_fallback(monkeypatch):
    db = FakeStateDB()
    db.connection = FakeTotalsConnection()
    monkeypatch.setattr(api_server, "_call_backfill_task", None, raising=False)
    monkeypatch.setattr(
        api_server,
        "_call_backfill_last_status",
        {
            "started_at": "2026-05-25T00:00:00+00:00",
            "finished_at": "2026-05-25T00:00:10+00:00",
            "result": {"ok": True, "calls_processed": 2},
            "error": "",
        },
        raising=False,
    )

    status = await api_server._build_amocrm_call_analysis_status(db)

    assert status["last_run"]["started_at"] == "2026-05-25T00:00:00+00:00"
    assert status["last_run"]["result"]["calls_processed"] == 2
