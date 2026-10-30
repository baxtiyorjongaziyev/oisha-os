"""Davr bo'yicha xodim kesimidagi xulosa — HR hisobot va Payroll uchun yagona manba.

Faqat faktlar: soat, daqiqa, kun soni. Jarima yoki ushlab qolish hisoblanmaydi —
bu qarorlar amaldagi mehnat qoidalari va tasdiqlangan siyosat asosida alohida qilinadi.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from src.services.core.attendance import repo, rules


@dataclass
class EmployeeSummary:
    employee_id: int
    name: str
    scheduled_days: int = 0
    present_days: int = 0
    on_time_days: int = 0
    late_days: int = 0
    late_minutes: int = 0
    early_leave_days: int = 0
    early_leave_minutes: int = 0
    absent_days: int = 0
    approved_leave_days: int = 0
    pending_review: int = 0
    worked_minutes: int = 0
    overtime_minutes: int = 0
    missing_check_out: int = 0

    @property
    def worked_hours(self) -> float:
        return round(self.worked_minutes / 60, 2)

    def as_dict(self) -> dict:
        return {**asdict(self), "worked_hours": self.worked_hours,
                "overtime_hours": round(self.overtime_minutes / 60, 2)}


def _days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _apply_day(s: EmployeeSummary, shift: rules.Shift, day: date, cal: rules.Calendar,
               events: dict, override: str | None, counted_until: date) -> None:
    ci, co = events.get("check_in"), events.get("check_out")
    required = rules.is_required_day(shift, day, cal)
    if required:
        s.scheduled_days += 1
    if override == rules.APPROVED_LEAVE:
        s.approved_leave_days += 1
        return
    if ci is None:
        if required and day <= counted_until and override not in (rules.DAY_OFF, rules.ON_TIME):
            s.absent_days += 1
        return
    s.present_days += 1
    status = ci["status"]
    if status == rules.ON_TIME:
        s.on_time_days += 1
    elif status == rules.LATE:
        s.late_days += 1
        s.late_minutes += int(ci["minutes_late"])
    if rules.PENDING_REVIEW in (status, co["status"] if co else None):
        s.pending_review += 1
    if co is None:
        s.missing_check_out += 1
        return
    if co["status"] == rules.EARLY_LEAVE:
        s.early_leave_days += 1
        s.early_leave_minutes += int(co["minutes_early"])
    worked, overtime = rules.worked_minutes(
        shift, datetime.fromisoformat(ci["server_ts"]), datetime.fromisoformat(co["server_ts"]))
    s.worked_minutes += worked
    s.overtime_minutes += overtime


async def period_summary(db, start: date, end: date, cal: rules.Calendar | None = None,
                         today: date | None = None, employee_id: int | None = None) -> list[dict]:
    """Faqat davomat ishga tushgan kundan ``today`` gacha bo'lgan kunlar hisoblanadi."""
    cal = cal or rules.Calendar()
    counted_until = min(end, today or date.today())
    live = await repo.go_live_date(db)
    if live:
        start = max(start, date.fromisoformat(live))
    events: dict[tuple[int, str], dict] = {}
    for r in await repo.events_between(db, start.isoformat(), end.isoformat(), employee_id):
        events.setdefault((int(r["employee_id"]), r["work_date"]), {})[r["kind"]] = r
    overrides = {(int(r["employee_id"]), r["work_date"]): r["new_status"]
                 for r in await repo.day_corrections(db, start.isoformat(), end.isoformat())}
    out = []
    for emp in await repo.employees_active(db):
        emp_id = int(emp["id"])
        if employee_id is not None and emp_id != employee_id:
            continue
        s = EmployeeSummary(emp_id, str(emp["name"]))
        for day in _days(start, end):
            iso = day.isoformat()
            shift = rules.shift_from_row(await repo.employee_shift(db, emp_id, iso))
            _apply_day(s, shift, day, cal, events.get((emp_id, iso), {}), overrides.get((emp_id, iso)),
                       counted_until)
        out.append(s.as_dict())
    return out
