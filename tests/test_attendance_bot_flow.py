"""Davomat Telegram oqimi: ulanish so'rovi, owner tasdig'i, keldi/ketdi xabari, hisobotlar."""
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from src.services.core.attendance import admin, bot_flow
from src.services.core.attendance.notifier import format_event
from src.services.core.attendance.schema import init_attendance_tables
from src.services.core.attendance.service import Actor, AttendanceError, AttendanceService

LAT, LON = 40.4710, 71.7240
TZ5 = timezone(timedelta(hours=5))


class SqliteDb:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE,"
                          " name TEXT NOT NULL, role TEXT NOT NULL, is_active INTEGER DEFAULT 1)")

    async def execute(self, q, p=None):
        return self.conn.execute(q, p or []).fetchall()

    async def commit(self):
        self.conn.commit()

    async def rollback(self):
        self.conn.rollback()


class EventNotifier:
    def __init__(self):
        self.events, self.reviews = [], []

    async def notify_review(self, text):
        self.reviews.append(text)
        return True

    async def notify_event(self, text):
        self.events.append(text)
        return True


@pytest.fixture
async def db():
    d = SqliteDb()
    await init_attendance_tables(d)
    await admin.configure_office(d, actor="owner", name="Ofis", latitude=LAT, longitude=LON,
                                 radius_m=100, max_accuracy_m=50)
    return d


async def test_link_request_approve_creates_employee(db):
    req = await bot_flow.request_link(db, 777, "Rayxona Rahimova")
    text, tg = await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_APPROVE}{req['id']}")
    assert tg == 777 and "ulandi" in text
    row = db.conn.execute("SELECT name, telegram_id FROM employees").fetchone()
    assert tuple(row) == ("Rayxona Rahimova", 777)


async def test_link_reject(db):
    req = await bot_flow.request_link(db, 778, "Begona")
    text, tg = await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_REJECT}{req['id']}")
    assert "rad" in text and db.conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0


async def test_double_decision_is_rejected(db):
    req = await bot_flow.request_link(db, 779, "Shahnoza Abdijabborova")
    await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_APPROVE}{req['id']}")
    with pytest.raises(AttendanceError):
        await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_APPROVE}{req['id']}")


async def test_already_linked_cannot_request_again(db):
    req = await bot_flow.request_link(db, 780, "Mumtozmaxal Normurodova")
    await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_APPROVE}{req['id']}")
    with pytest.raises(AttendanceError) as e:
        await bot_flow.request_link(db, 780, "Mumtozmaxal")
    assert "ulangansiz" in bot_flow.error_text(e.value)


def test_owner_buttons_shape():
    kb = bot_flow.owner_buttons(5)["inline_keyboard"][0]
    assert [b["callback_data"] for b in kb] == ["att_link:ok:5", "att_link:no:5"]


def test_format_event():
    assert format_event("Rayxona", "check_in", "09:58", 0, 0) == "✅ Rayxona keldi — 09:58 (vaqtida)"
    assert format_event("Mumtoz", "check_in", "10:17", 17, 0) == "⏰ Mumtoz keldi — 10:17 (17 daq kech)"
    assert format_event("Shahnoza", "check_out", "19:05", 0, 0) == "👋 Shahnoza ketdi — 19:05"


async def test_auto_punch_sends_event_and_today_report(db):
    req = await bot_flow.request_link(db, 777, "Rayxona Rahimova")
    await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_APPROVE}{req['id']}")
    notifier = EventNotifier()
    clock = lambda: datetime(2026, 10, 22, 10, 12, tzinfo=TZ5)  # noqa: E731
    svc = AttendanceService(db, clock=clock, notifier=notifier)
    await svc.auto_punch(Actor(1, "Rayxona Rahimova", "777"), "check_in", "auto-test-0001", "telegram_live_location")
    assert notifier.events == ["⏰ Rayxona Rahimova keldi — 10:12 (12 daq kech)"]
    text = await bot_flow.today_text(db, date(2026, 10, 22))
    assert "Rayxona Rahimova — keldi 10:12, 12 daq kech, hali ishda" in text


async def test_today_report_without_employees(db):
    assert "/ulanish" in await bot_flow.today_text(db, date(2026, 10, 22))


async def test_month_report(db):
    req = await bot_flow.request_link(db, 777, "Rayxona Rahimova")
    await bot_flow.decide(db, actor="1", data=f"{bot_flow.CB_APPROVE}{req['id']}")
    text = await bot_flow.month_text(db, date(2026, 10, 22))
    assert "Rayxona Rahimova" in text and "kun" in text
