import sqlite3
from datetime import datetime, timedelta

import pytest

from src.services.core.community_sync.merge import Conflict
from src.services.core.community_sync.models import Person
from src.services.core.community_sync.store import SyncStore


def fake_exec():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    async def execute(sql, params=None):
        cur = conn.execute(sql, params or [])
        conn.commit()
        return [dict(r) for r in cur.fetchall()]

    return execute


@pytest.fixture
async def store():
    s = SyncStore(execute=fake_exec())
    await s.ensure_schema()
    return s


async def test_person_roundtrip(store):
    p = Person(key="tg:1", tg_id=1, first_name="Ali", cohorts={"TN7"}, ext={"google": "people/c1"})
    await store.upsert_person(p)
    p.phone = "+998901112233"
    await store.upsert_person(p)
    got = (await store.load_people())["tg:1"]
    assert got.phone == "+998901112233" and got.cohorts == {"TN7"} and got.ext == {"google": "people/c1"}


async def test_snapshot_overwrite(store):
    await store.save_snapshot("google", "k", {"phone": "1"})
    await store.save_snapshot("google", "k", {"phone": "2"})
    assert (await store.load_snapshots()) == {"google": {"k": {"phone": "2"}}}


async def test_due_tg_respects_wait_and_limit(store):
    now = datetime(2026, 11, 17, 10)
    for i in range(3):
        await store.enqueue_tg(f"k{i}", f"u{i}", "")
    await store.mark_tg("k0", "deferred", now + timedelta(hours=1))
    await store.mark_tg("k1", "done")
    await store.enqueue_tg("k1", "u1", "")  # qayta navbatga qöshilmaydi
    due = await store.due_tg(10, now)
    assert [d["key"] for d in due] == ["k2"]
    assert len(await store.due_tg(10, now + timedelta(hours=2))) == 2
    assert len(await store.due_tg(1, now + timedelta(hours=2))) == 1


async def test_conflicts(store):
    await store.add_conflict(Conflict("k", "first_name", {"google": "B", "amocrm": "C"}))
    assert (await store.open_conflicts())[0].values == {"google": "B", "amocrm": "C"}
    await store.resolve_conflict("k", "first_name", "B")
    assert await store.open_conflicts() == []
    assert await store.resolved_values() == {"k": {"first_name": "B"}}
