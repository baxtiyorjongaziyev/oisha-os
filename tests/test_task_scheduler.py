"""Tests for task_scheduler — working hours logic."""

from datetime import datetime, timedelta, timezone

import pytest

from src.utils.task_scheduler import (
    TASHKENT_TZ,
    WORK_END_HOUR,
    WORK_START_HOUR,
    WORKING_DAYS,
    hours_until_work,
    is_working_hours,
    next_work_slot,
    spread_tasks,
    task_deadline,
)


class TestNextWorkSlot:
    def test_returns_working_hours(self):
        slot = next_work_slot()
        assert WORK_START_HOUR <= slot.hour < WORK_END_HOUR

    def test_returns_working_day(self):
        slot = next_work_slot()
        assert slot.weekday() in WORKING_DAYS

    def test_has_timezone(self):
        slot = next_work_slot()
        assert slot.tzinfo is not None

    def test_after_work_end_goes_to_next_day(self):
        # 18:00 Toshkent — ish tugagan, keyingi ish kuniga
        after = datetime(2026, 6, 24, 18, 0, tzinfo=TASHKENT_TZ)  # Chorshanba
        slot = next_work_slot(after=after)
        assert slot.hour == WORK_START_HOUR
        # Keyingi kun — Payshanba (4)
        assert slot.day == 25

    def test_saturday_is_working_day(self):
        # Shanba 12:00 — ish kuni (0-5 range)
        after = datetime(2026, 6, 27, 12, 0, tzinfo=TASHKENT_TZ)  # Shanba (weekday=5)
        slot = next_work_slot(after=after)
        assert slot.weekday() == 5  # Shanba ish kuni
        assert WORK_START_HOUR <= slot.hour < WORK_END_HOUR

    def test_sunday_goes_to_monday(self):
        # Yakshanba
        after = datetime(2026, 6, 28, 10, 0, tzinfo=TASHKENT_TZ)  # Yakshanba
        slot = next_work_slot(after=after)
        assert slot.weekday() == 0

    def test_before_work_start_goes_to_start(self):
        # 09:00 — ish boshlanmagan
        after = datetime(2026, 6, 24, 9, 0, tzinfo=TASHKENT_TZ)
        slot = next_work_slot(after=after)
        assert slot.hour == WORK_START_HOUR
        assert slot.minute == 0

    def test_during_work_returns_same_day(self):
        # 14:00 — ish vaqti
        after = datetime(2026, 6, 24, 14, 0, tzinfo=TASHKENT_TZ)
        slot = next_work_slot(after=after)
        assert slot.day == 24
        assert WORK_START_HOUR <= slot.hour < WORK_END_HOUR


class TestSpreadTasks:
    def test_spread_tasks_count(self):
        slots = spread_tasks(5)
        assert len(slots) == 5

    def test_spread_tasks_unique(self):
        slots = spread_tasks(10)
        times = [s.isoformat() for s in slots]
        assert len(times) == len(set(times))

    def test_spread_tasks_within_working_hours(self):
        slots = spread_tasks(10)
        for slot in slots:
            assert WORK_START_HOUR <= slot.hour < WORK_END_HOUR
            assert slot.weekday() in WORKING_DAYS


class TestTaskDeadline:
    def test_deadline_in_future(self):
        deadline_ts = task_deadline(due_in_hours=24)
        now_ts = int(datetime.now(TASHKENT_TZ).timestamp())
        assert deadline_ts > now_ts

    def test_deadline_within_working_hours(self):
        deadline_ts = task_deadline(due_in_hours=1)
        deadline_dt = datetime.fromtimestamp(deadline_ts, tz=TASHKENT_TZ)
        assert WORK_START_HOUR <= deadline_dt.hour < WORK_END_HOUR


class TestIsWorkingHours:
    def test_returns_bool(self):
        result = is_working_hours()
        assert isinstance(result, bool)


class TestHoursUntilWork:
    def test_returns_float(self):
        result = hours_until_work()
        assert isinstance(result, float)
        assert result >= 0
