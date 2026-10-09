import asyncio
import sqlite3

from src.services.call_analytics.crm_actions import FieldFillAction, StageAction
from src.services.call_analytics.crm_automation_store import DbCrmAutomationStore
from src.services.call_analytics.crm_executor import CrmActionExecutor
from tests.test_crm_executor import FakeAmo


class FakeDb:
    def __init__(self, state=None):
        self.conn = sqlite3.connect(":memory:")
        self.state = state or {}

    def get_connection(self):
        return self.conn

    async def get_state(self, key, default=None):
        return self.state.get(key, default)


def _store(enabled="true"):
    store = DbCrmAutomationStore(FakeDb({"crm_automation:enabled": enabled}))
    asyncio.run(store.initialize())
    return store


def test_kill_switch_defaults_off():
    store = DbCrmAutomationStore(FakeDb())
    assert asyncio.run(store.is_enabled()) is False
    assert asyncio.run(_store("on").is_enabled()) is True


def test_record_get_and_count_recent():
    store = _store()
    audit_id = asyncio.run(
        store.record({"lead_id": 5, "action": "StageAction", "before": {"status_id": 1},
                      "after": {"status_id": 2}, "success": True, "dry_run": False})
    )
    row = asyncio.run(store.get(audit_id))
    assert row["before"] == {"status_id": 1} and row["success"] is True
    assert asyncio.run(store.count_recent(5, 3600)) == 1
    assert asyncio.run(store.count_recent(6, 3600)) == 0


def test_dry_run_rows_do_not_count_toward_rate_limit():
    store = _store()
    asyncio.run(store.record({"lead_id": 5, "action": "x", "success": True, "dry_run": True}))
    assert asyncio.run(store.count_recent(5, 3600)) == 0


def test_executor_roundtrip_with_db_store():
    store, amo = _store(), FakeAmo()
    executor = CrmActionExecutor(amo, store)
    result = asyncio.run(executor.execute(9, [FieldFillAction(101, "Acme"), StageAction(20, 30)]))
    assert len(result.audit_ids) == 2
    amo.calls.clear()
    assert asyncio.run(executor.rollback(result.audit_ids[1])) is True
    assert amo.calls == [("status", 9, 20)]
    assert asyncio.run(store.get(result.audit_ids[1]))["rolled_back"] is True
