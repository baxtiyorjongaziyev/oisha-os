import asyncio

import pytest
from unittest.mock import patch

from src import api_server
from src.api.routes.state import api_state


@pytest.mark.asyncio
async def test_health_snapshot_uses_cached_storage_when_turso_query_times_out(monkeypatch):
    class SlowDatabase:
        db_path = "/tmp/placeholder.db"

        async def get_recent_job_runs(self, limit=10):
            await asyncio.sleep(0.05)
            return []

        async def get_storage_counts(self):
            return {}

    monkeypatch.setattr(api_state, "db_instance", SlowDatabase())
    monkeypatch.setattr(api_state, "_HEALTH_DB_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(
        api_state,
        "_health_db_snapshot_cache",
        {
            "recent_job_runs": [{"job_name": "cached"}],
            "storage_counts": {"agent_actions": 7, "call_analyses": 2},
            "updated_at": "2026-06-01T00:00:00+05:00",
        },
    )

    with patch(
        "src.services.core.agent_runtime.get_runtime_context",
        return_value={"state_backend": "turso", "state_db_path": "/tmp/placeholder.db"},
    ):
        snapshot = await api_server.build_health_snapshot()

    assert snapshot["storage"]["cached"] is True
    assert snapshot["storage"]["agent_action_rows"] == 7
    assert snapshot["storage"]["call_analysis_rows"] == 2
    assert snapshot["storage"]["recent_job_runs"] == [{"job_name": "cached"}]


@pytest.mark.asyncio
async def test_health_snapshot_refreshes_storage_cache(monkeypatch):
    class FastDatabase:
        db_path = "/tmp/placeholder.db"

        async def get_recent_job_runs(self, limit=10):
            return [{"job_name": "fresh"}]

        async def get_storage_counts(self):
            return {"kv_settings": 3}

    monkeypatch.setattr(api_state, "db_instance", FastDatabase())
    monkeypatch.setattr(api_state, "_HEALTH_DB_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(
        api_state,
        "_health_db_snapshot_cache",
        {"recent_job_runs": [], "storage_counts": {}, "updated_at": None},
    )
    with patch(
        "src.services.core.agent_runtime.get_runtime_context",
        return_value={"state_backend": "turso", "state_db_path": "/tmp/placeholder.db"},
    ):
        snapshot = await api_server.build_health_snapshot()

    assert snapshot["storage"]["cached"] is False
    assert snapshot["storage"]["kv_rows"] == 3
    assert snapshot["storage"]["recent_job_runs"] == [{"job_name": "fresh"}]
    assert snapshot["storage"]["cache_updated_at"]
