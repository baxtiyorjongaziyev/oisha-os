"""Avtomatik keldi/ketdi: Telegram jonli lokatsiya va ofis Wi-Fi (in-memory SQLite)."""
import sqlite3
import time as _time
from datetime import datetime, timedelta, timezone

import pytest

from src.services.core.attendance import admin, auto_presence as ap
from src.services.core.attendance.schema import init_attendance_tables
from src.services.core.attendance.service import AttendanceService

LAT, LON = 40.4710, 71.7240
FAR_LAT = 40.4810  # ~1.1 km shimolda
TZ5 = timezone(timedelta(hours=5))


class SqliteDb:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE,"
                          " name TEXT, role TEXT, is_active INTEGER DEFAULT 1)")
        self.conn.execute("INSERT INTO employees VALUES (1, 111, 'Rayxona', 'sales', 1)")

    async def execute(self, q, p=None):
        return self.conn.execute(q, p or []).fetchall()

    async def commit(self):
        self.conn.commit()

    async def rollback(self):
        self.conn.rollback()


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
async def env(monkeypatch):
    db = SqliteDb()
    await init_attendance_tables(db)
    await admin.configure_office(db, actor="owner", name="Ofis", latitude=LAT, longitude=LON,
                                 radius_m=100, max_accuracy_m=50)
    clock = Clock(datetime(2026, 10, 22, 9, 55, tzinfo=TZ5))
    svc = AttendanceService(db, clock=clock)
    epoch = {"t": 1_800_000_000}
    monkeypatch.setattr(ap.time, "time", lambda: epoch["t"])
    return db, svc, clock, epoch


def events(db):
    return [r["kind"] for r in db.conn.execute("SELECT kind FROM attendance_events ORDER BY id")]


async def loc(db, svc, clock, lat, acc=15.0, tg=111):
    return await ap.on_location(db, tg, lat, LON, acc, service=svc, now_local=clock())


async def test_live_location_inside_checks_in_once(env):
    db, svc, clock, _ = env
    assert await loc(db, svc, clock, LAT) == "check_in"
    assert await loc(db, svc, clock, LAT) is None
    assert events(db) == ["check_in"]


async def test_coordinates_are_never_stored(env):
    db, svc, clock, _ = env
    await loc(db, svc, clock, LAT + 0.0001)  # ofis markazidan farqli nuqta
    stored = []
    for table in ("attendance_auto_state", "attendance_verifications", "attendance_audit_logs",
                  "attendance_events", "attendance_sessions"):
        stored += [str(tuple(r)) for r in db.conn.execute(f"SELECT * FROM {table}")]  # noqa: S608
    dump = "\n".join(stored)
    assert stored and "40.4711" not in dump and "71.724" not in dump


async def test_unknown_telegram_user_ignored(env):
    db, svc, clock, _ = env
    assert await loc(db, svc, clock, LAT, tg=999) is None
    assert events(db) == []


async def test_low_accuracy_does_nothing(env):
    db, svc, clock, _ = env
    assert await loc(db, svc, clock, LAT, acc=400) is None


async def test_daytime_exit_is_a_break_not_checkout(env):
    db, svc, clock, epoch = env
    await loc(db, svc, clock, LAT)
    clock.t = datetime(2026, 10, 22, 13, 0, tzinfo=TZ5)
    await loc(db, svc, clock, FAR_LAT)
    epoch["t"] += 3600
    assert await loc(db, svc, clock, FAR_LAT) is None
    assert events(db) == ["check_in"]


async def test_evening_exit_checks_out_after_15_min(env):
    db, svc, clock, epoch = env
    await loc(db, svc, clock, LAT)
    clock.t = datetime(2026, 10, 22, 19, 5, tzinfo=TZ5)
    assert await loc(db, svc, clock, FAR_LAT) is None  # endi chiqdi
    epoch["t"] += 10 * 60
    assert await loc(db, svc, clock, FAR_LAT) is None
    epoch["t"] += 6 * 60
    assert await loc(db, svc, clock, FAR_LAT) == "check_out"
    assert events(db) == ["check_in", "check_out"]


async def test_coming_back_resets_exit_timer(env):
    db, svc, clock, epoch = env
    await loc(db, svc, clock, LAT)
    clock.t = datetime(2026, 10, 22, 18, 0, tzinfo=TZ5)
    await loc(db, svc, clock, FAR_LAT)
    epoch["t"] += 10 * 60
    await loc(db, svc, clock, LAT)
    epoch["t"] += 10 * 60
    assert await loc(db, svc, clock, FAR_LAT) is None
    assert events(db) == ["check_in"]


async def test_outside_work_window_ignored(env):
    db, svc, clock, _ = env
    clock.t = datetime(2026, 10, 22, 6, 30, tzinfo=TZ5)
    assert await loc(db, svc, clock, LAT) is None


async def test_wifi_join_requires_office_ip(env):
    db, svc, clock, _ = env
    token = await ap.create_token(db, actor="owner", employee_id=1)
    actor = await ap.employee_for_token(db, token)
    assert actor.name == "Rayxona"
    assert await ap.on_wifi(db, actor, "join", False, service=svc, now_local=clock()) is None
    assert await ap.on_wifi(db, actor, "join", True, service=svc, now_local=clock()) == "check_in"
    clock.t = datetime(2026, 10, 22, 12, 0, tzinfo=TZ5)
    assert await ap.on_wifi(db, actor, "leave", None, service=svc, now_local=clock()) is None  # tanaffus
    clock.t = datetime(2026, 10, 22, 19, 10, tzinfo=TZ5)
    assert await ap.on_wifi(db, actor, "leave", None, service=svc, now_local=clock()) == "check_out"


async def test_wifi_token_rotation_and_bad_token(env):
    db, *_ = env
    old = await ap.create_token(db, actor="owner", employee_id=1)
    new = await ap.create_token(db, actor="owner", employee_id=1)
    assert await ap.employee_for_token(db, old) is None
    assert await ap.employee_for_token(db, new) is not None
    assert await ap.employee_for_token(db, "oaw_nope") is None
    assert "oaw_" not in "\n".join(db.conn.iterdump())  # faqat xesh saqlanadi


def test_classify_boundary():
    from src.services.core.attendance.geofence import Geofence

    fence = Geofence(LAT, LON, 100, 50)
    assert ap.classify(fence, LAT, LON, 10) is True
    assert ap.classify(fence, FAR_LAT, LON, 10) is False
    assert ap.classify(fence, LAT + 0.0009, LON, 30) is None  # ~100 m — chegara


def test_time_module_patched_only_in_fixture():
    assert ap.time is _time
