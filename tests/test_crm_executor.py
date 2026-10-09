import asyncio

from src.services.call_analytics.crm_actions import (
    FieldFillAction,
    FieldSuggestion,
    StageAction,
    TaskAction,
)
from src.services.call_analytics.crm_executor import CrmActionExecutor


class FakeAmo:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    async def update_lead_custom_fields(self, lead_id, fields):
        self.calls.append(("fields", lead_id, dict(fields)))
        return self.ok

    async def update_lead_status(self, lead_id, status_id):
        self.calls.append(("status", lead_id, status_id))
        return self.ok

    async def create_task(self, element_id, text, complete_till, responsible_user_id=None):
        self.calls.append(("task", element_id, text))
        return {"id": 77}


class FakeStore:
    def __init__(self, enabled=True, recent=0):
        self.enabled = enabled
        self.recent = recent
        self.rows = {}

    async def is_enabled(self):
        return self.enabled

    async def count_recent(self, lead_id, window_seconds):
        return self.recent

    async def record(self, entry):
        audit_id = len(self.rows) + 1
        self.rows[audit_id] = dict(entry, rolled_back=False)
        return audit_id

    async def get(self, audit_id):
        return self.rows.get(audit_id)

    async def mark_rolled_back(self, audit_id):
        self.rows[audit_id]["rolled_back"] = True


def _run(coro):
    return asyncio.run(coro)


ACTIONS = [
    FieldFillAction(field_id=101, value="Acme"),
    FieldSuggestion(field_id=102, current="Manager", proposed="CEO"),
    StageAction(from_status=20, to_status=30),
    TaskAction(text="Etapni tekshiring"),
]


def test_executes_all_actions_and_audits():
    amo, store = FakeAmo(), FakeStore()
    result = _run(CrmActionExecutor(amo, store).execute(1, ACTIONS))
    kinds = [c[0] for c in amo.calls]
    assert kinds == ["fields", "status", "task"]
    assert len(store.rows) == 3
    assert result.suggestions == ["102: Manager -> CEO"]


def test_kill_switch_blocks_everything():
    amo, store = FakeAmo(), FakeStore(enabled=False)
    result = _run(CrmActionExecutor(amo, store).execute(1, ACTIONS))
    assert amo.calls == [] and store.rows == {}
    assert result.skipped_reason == "disabled"


def test_rate_limit_blocks():
    amo, store = FakeAmo(), FakeStore(recent=3)
    result = _run(CrmActionExecutor(amo, store, max_changes_per_hour=3).execute(1, ACTIONS))
    assert amo.calls == []
    assert result.skipped_reason == "rate_limited"


def test_dry_run_audits_without_writing():
    amo, store = FakeAmo(), FakeStore()
    _run(CrmActionExecutor(amo, store, dry_run=True).execute(1, ACTIONS))
    assert amo.calls == []
    assert len(store.rows) == 3
    assert all(r["dry_run"] for r in store.rows.values())


def test_failed_write_is_audited_as_failed():
    amo, store = FakeAmo(ok=False), FakeStore()
    _run(CrmActionExecutor(amo, store).execute(1, [StageAction(20, 30)]))
    assert store.rows[1]["success"] is False


def test_rollback_stage_and_field():
    amo, store = FakeAmo(), FakeStore()
    executor = CrmActionExecutor(amo, store)
    _run(executor.execute(1, [FieldFillAction(101, "Acme"), StageAction(20, 30)]))
    amo.calls.clear()
    assert _run(executor.rollback(1)) is True
    assert _run(executor.rollback(2)) is True
    assert amo.calls == [("fields", 1, {101: ""}), ("status", 1, 20)]
    assert _run(executor.rollback(2)) is False  # ikkinchi marta yo'q
