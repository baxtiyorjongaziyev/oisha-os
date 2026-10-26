"""Lidni ishdagi sotuvchiga berish — in-memory SQLite, soxta amoCRM va guruh."""
from __future__ import annotations

import sqlite3

import pytest

from src.services.core.crm.amocrm_pipeline_config import SALES_NEW_STATUS_ID
from src.services.core.leads import assignment
from src.services.core.leads.assignment import LeadAssigner, lead_kind

TODAY = "2026-10-26"


class MemPool:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """CREATE TABLE employees (id INTEGER PRIMARY KEY, telegram_id INTEGER, name TEXT,
                   role TEXT, amo_id INTEGER, is_active BOOLEAN DEFAULT 1);
               CREATE TABLE attendance_events (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER,
                   kind TEXT, work_date TEXT, server_ts TEXT);"""
        )
        for i, (name, amo) in enumerate([("Mumtozmaxal", 101), ("Rayxona", 102), ("Shahnoza", 103)], 1):
            self.conn.execute("INSERT INTO employees(id,name,role,amo_id) VALUES (?,?,'sales',?)", [i, name, amo])

    def check(self, emp_id, kind, ts):
        self.conn.execute(
            "INSERT INTO attendance_events(employee_id,kind,work_date,server_ts) VALUES (?,?,?,?)",
            [emp_id, kind, TODAY, ts],
        )

    async def execute(self, query, params=None):
        return [dict(r) for r in self.conn.execute(query, params or []).fetchall()]

    async def commit(self):
        self.conn.commit()


class FakeAmo:
    def __init__(self):
        self.responsible = {}
        self.status = {}
        self.tags = []
        self.tag_ok = True

    async def add_lead_tag(self, lead_id, tag):
        self.tags.append((lead_id, tag))
        return self.tag_ok

    def update_lead_responsible(self, lead_id, user_id):
        self.responsible[lead_id] = user_id
        return True

    async def get_lead(self, lead_id):
        return {"id": lead_id, "status_id": self.status.get(lead_id, SALES_NEW_STATUS_ID)}


class FakeNow:
    def __init__(self, d):
        self._d = d

    def date(self):
        return self._d


@pytest.fixture
def env(monkeypatch):
    import datetime

    monkeypatch.setattr(assignment, "get_local_now", lambda: FakeNow(datetime.date(2026, 10, 26)))
    monkeypatch.setattr(assignment, "is_quiet_hours", lambda: False)
    clock = {"t": 1_800_000_000}
    monkeypatch.setattr(assignment.time, "time", lambda: clock["t"])
    pool, amo, sent = MemPool(), FakeAmo(), []
    a = LeadAssigner(amo, pool, notify=lambda text, lead_id: sent.append((lead_id, text)) or True)
    return pool, amo, sent, a, clock


def test_kind_by_source():
    assert lead_kind("meta_lead_ads") == "new"
    assert lead_kind("telegram_dm") == "new"
    assert lead_kind("telegram_group_tn5") == "networking"


async def test_new_lead_goes_to_on_duty_new_seller_not_shahnoza(env):
    pool, amo, sent, a, _ = env
    pool.check(3, "check_in", "09:50")  # Shahnoza ishda
    pool.check(2, "check_in", "10:00")  # Rayxona ishda
    assert await a.assign_new(1, "Ali", "meta_lead_ads") == "Rayxona"
    assert amo.responsible == {1: 102}
    assert "Rayxona" in sent[0][1] and "Ali" in sent[0][1]


async def test_checked_out_seller_is_not_on_duty(env):
    pool, amo, sent, a, _ = env
    pool.check(1, "check_in", "10:00")
    pool.check(1, "check_out", "13:00")  # Mumtozmaxal ketdi
    pool.check(2, "check_in", "10:05")
    assert await a.assign_new(1, "Ali", "telegram_dm") == "Rayxona"


async def test_balances_by_today_load(env):
    pool, amo, sent, a, _ = env
    pool.check(1, "check_in", "10:00")
    pool.check(2, "check_in", "10:00")
    got = [await a.assign_new(i, f"L{i}", "meta_lead_ads") for i in range(1, 5)]
    assert sorted(got) == ["Mumtozmaxal", "Mumtozmaxal", "Rayxona", "Rayxona"]


async def test_networking_prefers_shahnoza_then_falls_back(env):
    pool, amo, sent, a, _ = env
    pool.check(1, "check_in", "10:00")
    assert await a.assign_new(1, "Trening", "telegram_group_tn5") == "Mumtozmaxal"
    pool.check(3, "check_in", "11:00")
    assert await a.assign_new(2, "Trening2", "telegram_group_tn5") == "Shahnoza"


async def test_nobody_on_duty_then_first_arrival_gets_it(env):
    pool, amo, sent, a, _ = env
    assert await a.assign_new(1, "Ali", "meta_lead_ads") is None
    assert "ishda sotuvchi yo'q" in sent[0][1]
    pool.check(1, "check_in", "10:00")
    stats = await a.follow_up_once()
    assert stats["assigned"] == 1 and amo.responsible == {1: 101}


async def test_remind_after_30_then_reassign_after_60(env):
    pool, amo, sent, a, clock = env
    pool.check(1, "check_in", "10:00")
    pool.check(2, "check_in", "10:00")
    first = await a.assign_new(1, "Ali", "meta_lead_ads")
    clock["t"] += 31 * 60
    assert (await a.follow_up_once())["reminded"] == 1
    assert (await a.follow_up_once())["reminded"] == 0  # bir marta
    clock["t"] += 30 * 60
    assert (await a.follow_up_once())["reassigned"] == 1
    second = [n for n in ("Mumtozmaxal", "Rayxona") if n != first][0]
    assert amo.responsible[1] == {"Mumtozmaxal": 101, "Rayxona": 102}[second]
    clock["t"] += 2 * 3600
    assert (await a.follow_up_once())["reassigned"] == 0  # faqat bir marta


async def test_moved_out_of_new_stops_follow_up(env):
    pool, amo, sent, a, clock = env
    pool.check(1, "check_in", "10:00")
    await a.assign_new(1, "Ali", "meta_lead_ads")
    amo.status[1] = 1
    clock["t"] += 3 * 3600
    assert await a.follow_up_once() == {"assigned": 0, "reminded": 0, "reassigned": 0}


async def test_quiet_hours_no_messages(env, monkeypatch):
    pool, amo, sent, a, _ = env
    monkeypatch.setattr(assignment, "is_quiet_hours", lambda: True)
    assert await a.assign_new(1, "Ali", "meta_lead_ads") is None
    assert sent == []


async def test_hunter_assigns_new_deal(monkeypatch, env):
    from src.services.core.leads.hunter import Candidate, HunterWriter

    pool, amo, sent, a, _ = env
    pool.check(2, "check_in", "10:00")
    calls = []

    async def fake_assign(self, lead_id, name, source):
        calls.append((lead_id, name, source))

    monkeypatch.setattr(LeadAssigner, "assign_new", fake_assign)

    class Amo(FakeAmo):
        async def ensure_lead(self, **kw):
            return 9

        async def add_lead_tag(self, *a):
            return True

    monkeypatch.setenv("LEAD_ASSIGNMENT_ENABLED", "1")
    r = await HunterWriter(Amo(), pool).submit(Candidate(source="meta_lead_ads", name="Ali", phone="901234567"))
    assert r.state == "sent" and calls == [(9, "Ali", "meta_lead_ads")]


async def test_failed_reassign_stays_eligible(env):
    pool, amo, sent, a, clock = env
    pool.check(1, "check_in", "10:00")
    pool.check(2, "check_in", "10:00")
    first = await a.assign_new(1, "Ali", "meta_lead_ads")
    clock["t"] += 61 * 60
    ok = amo.update_lead_responsible
    amo.update_lead_responsible = lambda lead_id, user_id: False
    assert (await a.follow_up_once())["reassigned"] == 0
    amo.update_lead_responsible = ok
    assert (await a.follow_up_once())["reassigned"] == 1
    assert amo.responsible[1] != {"Mumtozmaxal": 101, "Rayxona": 102}[first]


async def test_failed_reminder_is_retried(env):
    pool, amo, sent, a, clock = env
    pool.check(1, "check_in", "10:00")
    await a.assign_new(1, "Ali", "meta_lead_ads")
    clock["t"] += 31 * 60
    a.notify = lambda text, lead_id: False
    assert (await a.follow_up_once())["reminded"] == 0
    a.notify = lambda text, lead_id: True
    assert (await a.follow_up_once())["reminded"] == 1


async def test_follow_up_rotates_past_batch_limit(env):
    pool, amo, sent, a, clock = env
    pool.check(1, "check_in", "10:00")
    for i in range(1, 53):
        await a.assign_new(i, f"L{i}", "meta_lead_ads")
    clock["t"] += 31 * 60
    first = (await a.follow_up_once())["reminded"]
    second = (await a.follow_up_once())["reminded"]
    assert (first, second) == (50, 2)


async def test_waiting_lead_progressed_in_crm_is_not_assigned(env):
    pool, amo, sent, a, _ = env
    assert await a.assign_new(1, "Ali", "meta_lead_ads") is None
    amo.status[1] = 1  # amoCRM'da qo'lda ishlandi
    pool.check(1, "check_in", "10:00")
    assert (await a.follow_up_once())["assigned"] == 0
    assert amo.responsible == {}


async def test_claimed_lead_is_not_assigned_twice(env):
    pool, amo, sent, a, _ = env
    pool.check(1, "check_in", "10:00")
    await a.init()
    pool.conn.execute(
        "INSERT INTO lead_assignments(lead_id,lead_name,source,kind,state,created_at) "
        "VALUES (1,'Ali','meta_lead_ads','new','unassigned',0)"
    )
    assert await a._claim(1, "unassigned")  # boshqa jarayon olib turibdi
    assert await a.assign_new(1, "Ali", "meta_lead_ads") is None
    assert (await a.follow_up_once())["assigned"] == 0
    assert amo.responsible == {}


async def test_seller_without_amo_user_gets_tag_only(env):
    pool, amo, sent, a, _ = env
    pool.conn.execute("UPDATE employees SET amo_id=NULL")  # amoCRM'da bitta pullik foydalanuvchi
    pool.check(2, "check_in", "10:00")
    assert await a.assign_new(1, "Ali", "meta_lead_ads") == "Rayxona"
    assert amo.tags == [(1, "sotuvchi:Rayxona")] and amo.responsible == {}


async def test_failed_tag_keeps_lead_waiting(env):
    pool, amo, sent, a, _ = env
    pool.check(2, "check_in", "10:00")
    amo.tag_ok = False
    assert await a.assign_new(1, "Ali", "meta_lead_ads") is None
    row = pool.conn.execute("SELECT state FROM lead_assignments WHERE lead_id=1").fetchone()
    assert row["state"] == "unassigned"


class _Owner:
    def __init__(self):
        self.sent = []

    async def notify_review(self, text):
        self.sent.append(text)
        return True


@pytest.fixture
def owner(monkeypatch):
    from src.services.core.attendance import notifier

    o = _Owner()
    monkeypatch.setattr(notifier, "default_notifier", lambda: o)
    return o


async def test_auto_mode_waits_for_first_seller_check_in(monkeypatch, owner):
    from src.services.core.leads.assignment import assignment_enabled

    monkeypatch.delenv("LEAD_ASSIGNMENT_ENABLED", raising=False)
    pool = MemPool()
    pool.conn.execute("INSERT INTO employees(id,name,role) VALUES (9,'Hasanboy Gaziyev','pm')")
    assert await assignment_enabled(pool) is False
    pool.check(9, "check_in", "10:00")  # sotuvchi emas
    assert await assignment_enabled(pool) is False
    pool.check(2, "check_in", "10:05")  # Rayxona
    assert await assignment_enabled(pool) is True
    assert await assignment_enabled(pool) is True
    assert len(owner.sent) == 1 and "Rayxona" in owner.sent[0]


async def test_explicit_switch_overrides_auto(monkeypatch, owner):
    from src.services.core.leads.assignment import assignment_enabled

    pool = MemPool()
    pool.check(2, "check_in", "10:05")
    monkeypatch.setenv("LEAD_ASSIGNMENT_ENABLED", "0")
    assert await assignment_enabled(pool) is False
    monkeypatch.setenv("LEAD_ASSIGNMENT_ENABLED", "1")
    assert await assignment_enabled(MemPool()) is True
    assert owner.sent == []


async def test_auto_mode_without_attendance_tables(monkeypatch):
    from src.services.core.leads.assignment import assignment_enabled

    class Empty:
        async def execute(self, q, p=None):
            raise RuntimeError("no such table")

    monkeypatch.setenv("LEAD_ASSIGNMENT_ENABLED", "auto")
    assert await assignment_enabled(Empty()) is False
