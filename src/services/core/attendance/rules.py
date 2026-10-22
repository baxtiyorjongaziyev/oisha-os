"""Attendance Rules Engine: smena, grace period, tungi smena, bayram va ta'tilni hisobga oladi.

Barcha vaqtlar filialning mahalliy vaqtida (default Asia/Tashkent) hisoblanadi; server UTC
vaqtni beradi, bu modul uni o'giradi. Natija faqat holat va daqiqalar — jarima hisoblamaydi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ON_TIME, LATE, EARLY_LEAVE, ABSENT = "ON_TIME", "LATE", "EARLY_LEAVE", "ABSENT"
APPROVED_LEAVE, DAY_OFF, PENDING_REVIEW = "APPROVED_LEAVE", "DAY_OFF", "PENDING_REVIEW"

# Owner tasdiqlagan ish vaqti (2026-10-22): 10:00–19:00. Ish kunlari aytilmagan — Du–Ju default.
DEFAULT_START, DEFAULT_END = time(10, 0), time(19, 0)
DEFAULT_WEEKDAYS = frozenset({1, 2, 3, 4, 5})  # ISO: 1=Du ... 7=Ya
DEFAULT_GRACE_MIN = 10
# Smena boshlanishidan shuncha oldin check-in qabul qilinadi.
EARLY_ARRIVAL_WINDOW = timedelta(hours=3)


@dataclass(frozen=True)
class Shift:
    start: time = DEFAULT_START
    end: time = DEFAULT_END
    weekdays: frozenset[int] = DEFAULT_WEEKDAYS
    timezone: str = "Asia/Tashkent"

    @property
    def crosses_midnight(self) -> bool:
        return self.end <= self.start

    def window(self, work_date: date) -> tuple[datetime, datetime]:
        tz = ZoneInfo(self.timezone)
        start = datetime.combine(work_date, self.start, tz)
        end_day = work_date + timedelta(days=1) if self.crosses_midnight else work_date
        return start, datetime.combine(end_day, self.end, tz)


@dataclass(frozen=True)
class Policy:
    grace_minutes: int = DEFAULT_GRACE_MIN
    early_leave_grace_minutes: int = 0


@dataclass(frozen=True)
class Calendar:
    holidays: frozenset[date] = frozenset()
    approved_leave: frozenset[date] = frozenset()


@dataclass
class Classification:
    status: str
    work_date: date
    minutes_late: int = 0
    minutes_early: int = 0
    notes: list[str] = field(default_factory=list)


def is_working_day(shift: Shift, day: date, cal: Calendar) -> bool:
    return day.isoweekday() in shift.weekdays and day not in cal.holidays


def resolve_work_date(shift: Shift, at: datetime) -> date:
    """Tungi smenada 02:00 dagi check-out kechagi ish kuniga tegishli."""
    local = at.astimezone(ZoneInfo(shift.timezone))
    if shift.crosses_midnight and local.time() < shift.end:
        return local.date() - timedelta(days=1)
    if not shift.crosses_midnight:
        return local.date()
    start_today, _ = shift.window(local.date())
    return local.date() if local >= start_today - EARLY_ARRIVAL_WINDOW else local.date() - timedelta(days=1)


def _minutes(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() // 60))


def classify_check_in(shift: Shift, policy: Policy, cal: Calendar, at: datetime) -> Classification:
    work_date = resolve_work_date(shift, at)
    if work_date in cal.approved_leave:
        return Classification(PENDING_REVIEW, work_date, notes=["check_in_during_approved_leave"])
    if not is_working_day(shift, work_date, cal):
        return Classification(PENDING_REVIEW, work_date, notes=["check_in_on_day_off"])
    start, _ = shift.window(work_date)
    late = _minutes(at - start)
    if late <= policy.grace_minutes:
        return Classification(ON_TIME, work_date)
    return Classification(LATE, work_date, minutes_late=late)


def classify_check_out(shift: Shift, policy: Policy, cal: Calendar, at: datetime) -> Classification:
    work_date = resolve_work_date(shift, at)
    if not is_working_day(shift, work_date, cal) or work_date in cal.approved_leave:
        return Classification(PENDING_REVIEW, work_date, notes=["check_out_outside_schedule"])
    _, end = shift.window(work_date)
    early = _minutes(end - at)
    if early <= policy.early_leave_grace_minutes:
        return Classification(ON_TIME, work_date)
    return Classification(EARLY_LEAVE, work_date, minutes_early=early)


def classify_day_without_check_in(shift: Shift, cal: Calendar, day: date) -> str:
    """Kun tugaganda check-in bo'lmagan xodim uchun yakuniy holat."""
    if day in cal.approved_leave:
        return APPROVED_LEAVE
    if not is_working_day(shift, day, cal):
        return DAY_OFF
    return ABSENT


def worked_minutes(shift: Shift, check_in: datetime, check_out: datetime) -> tuple[int, int]:
    """(ishlangan daqiqa, smena oxiridan keyingi overtime daqiqa). Overtime faqat ma'lumot."""
    if check_out <= check_in:
        return 0, 0
    _, end = shift.window(resolve_work_date(shift, check_in))
    return _minutes(check_out - check_in), _minutes(check_out - max(end, check_in))
