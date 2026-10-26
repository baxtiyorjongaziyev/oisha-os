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
