from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.services.core.community_sync.approval import (
    APPROVE_KEY, handle_callback, is_approved,
)
from src.services.core.community_sync.merge import Conflict
from src.services.core.community_sync.models import Person
from src.services.core.community_sync.runner import Deps, run_once
from src.services.core.community_sync.store import SyncStore
from tests.test_community_sync_store import fake_exec

NOON = datetime(2026, 11, 17, 12)


class FakeAdapter:
    fields = ("first_name", "last_name", "phone")

    def __init__(self, name, rows=None, fail=False):
        self.name, self.rows, self.fail = name, rows or {}, fail
        self.applied = []

    async def read_all(self, people):
        return self.rows

    async def apply(self, changes, people):
        if self.fail:
            raise RuntimeError("down")
        self.applied.extend(changes)
        keys = sorted({c.key for c in changes})
        for k in keys:  # tizim endi kanonik qiymatni saqlaydi
            self.rows[k] = {f: getattr(people[k], f) for f in self.fields}
        return {"ok": len(keys), "failed": 0, "deferred": 0, "keys": keys}


def people(n):
    return [Person(key=f"tg:{i}", tg_id=i, first_name=f"A{i}", cohorts={"TN7"}) for i in range(n)]


async def deps(n=2, adapters=None, **cfg):
    store = SyncStore(execute=fake_exec())
    await store.ensure_schema()
    conf = dict(enabled=True, dry_run=False, bulk_threshold=20, tg_daily_limit=120, folder_id=13)
    conf.update(cfg)
    return Deps(
        store=store,
        collect=AsyncMock(return_value=people(n)),
        adapters=adapters if adapters is not None else [FakeAdapter("google")],
        notify=AsyncMock(),
        drip=AsyncMock(return_value={"ok": 0, "failed": 0, "deferred": 0}),
        **conf,
    )


async def test_disabled():
    d = await deps(enabled=False)
    assert (await run_once(d, now=NOON))["status"] == "disabled"
    d.collect.assert_not_awaited()


async def test_quiet_hours_blocks():
    d = await deps()
    res = await run_once(d, now=datetime(2026, 11, 17, 23, 30))
    assert res["status"] == "quiet_hours"
    d.collect.assert_not_awaited()


async def test_dry_run_no_writes():
    g = FakeAdapter("google")
    d = await deps(adapters=[g], dry_run=True)
    res = await run_once(d, now=NOON)
    assert res["status"] == "dry_run" and res["plan"] == {"google": 2}
    assert g.applied == [] and await d.store.load_people() == {}
    d.notify.assert_awaited()


async def test_bulk_needs_approval():
    g = FakeAdapter("google")
    d = await deps(n=25, adapters=[g])
    res = await run_once(d, now=NOON)
    assert res["status"] == "awaiting_approval" and g.applied == []
    await handle_callback("cs:approve", d.store, now=NOON)
    assert await is_approved(d.store, NOON)
    res = await run_once(d, now=NOON)
    assert res["status"] == "applied" and len({c.key for c in g.applied}) == 25


async def test_adapter_failure_isolated():
    bad, good = FakeAdapter("amocrm", fail=True), FakeAdapter("google")
    d = await deps(adapters=[bad, good])
    res = await run_once(d, now=NOON)
    assert res["status"] == "applied" and res["errors"] == ["amocrm"]
    assert len({c.key for c in good.applied}) == 2


async def test_idempotent_second_run_no_changes():
    g = FakeAdapter("google")
    d = await deps(adapters=[g])
    await run_once(d, now=NOON)
    g.applied.clear()
    res = await run_once(d, now=NOON)
    assert res["plan"] == {"google": 0} and g.applied == []


async def test_conflict_sent_and_resolved():
    g = FakeAdapter("google")
    a = FakeAdapter("amocrm")
    d = await deps(n=1, adapters=[g, a])
    await run_once(d, now=NOON)
    g.rows["tg:0"]["first_name"] = "B"
    a.rows["tg:0"]["first_name"] = "C"
    res = await run_once(d, now=NOON)
    assert res["conflicts"] == 1
    await handle_callback("cs:pick:tg:0:first_name:amocrm", d.store, now=NOON)
    g.applied.clear()
    await run_once(d, now=NOON)
    assert (await d.store.load_people())["tg:0"].first_name == "C"
    assert any(c.field == "first_name" and c.value == "C" for c in g.applied)


@pytest.mark.parametrize("data", ["cs:pick:bad", "other", "cs:pick:tg:0:first_name:nosuch"])
async def test_bad_callback_ignored(data):
    d = await deps()
    await d.store.add_conflict(Conflict("tg:0", "first_name", {"google": "B"}))
    assert await handle_callback(data, d.store, now=NOON) is False
    assert APPROVE_KEY


async def test_conflict_blocks_whole_key_write():
    g, a = FakeAdapter("google"), FakeAdapter("amocrm")
    d = await deps(n=1, adapters=[g, a])
    await run_once(d, now=NOON)
    g.rows["tg:0"]["last_name"] = "X"
    a.rows["tg:0"]["last_name"] = "Y"
    g.rows["tg:0"]["first_name"] = "Changed"
    g.applied.clear(); a.applied.clear()
    await run_once(d, now=NOON)
    assert g.applied == [] and a.applied == []


class FlakyAdapter(FakeAdapter):
    async def apply(self, changes, people):
        if not getattr(self, "ok_now", False):
            return {"ok": 0, "failed": 1, "deferred": 0, "keys": [], "written": {}}
        return await super().apply(changes, people)


async def test_failed_cohort_write_retried():
    g = FlakyAdapter("google")
    d = await deps(n=1, adapters=[g])
    await run_once(d, now=NOON)
    g.ok_now = True
    await run_once(d, now=NOON)
    assert any(c.field == "cohorts" for c in g.applied)


async def test_quiet_hours_reached_mid_run():
    g = FakeAdapter("google")
    d = await deps(adapters=[g])
    times = iter([NOON, datetime(2026, 11, 17, 23, 5)])
    d.clock = lambda: next(times, datetime(2026, 11, 17, 23, 5))
    res = await run_once(d)
    assert res["status"] == "quiet_hours" and g.applied == []


async def test_open_conflict_keeps_snapshot_baseline():
    g, a = FakeAdapter("google"), FakeAdapter("amocrm")
    d = await deps(n=1, adapters=[g, a])
    await run_once(d, now=NOON)
    g.rows["tg:0"]["first_name"] = "B"
    a.rows["tg:0"]["first_name"] = "C"
    for _ in range(3):  # owner javob bermadi
        res = await run_once(d, now=NOON)
    assert res["conflicts"] == 1
    assert g.rows["tg:0"]["first_name"] == "B" and a.rows["tg:0"]["first_name"] == "C"
