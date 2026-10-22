"""HR dashboard ko'rsatkichlari va hisobot qatorlari (faqat o'qish)."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.services.core.attendance import repo, rules


def _summary(rows: list, total: int, expected: set[int]) -> dict:
    check_ins = [r for r in rows if r["kind"] == "check_in"]
    present = {int(r["employee_id"]) for r in check_ins}
    late = [r for r in check_ins if r["status"] == rules.LATE]
    on_time = [r for r in check_ins if r["status"] == rules.ON_TIME]
    pending = [r for r in rows if r["status"] == rules.PENDING_REVIEW]
    return {
        "total_employees": total,
        "scheduled_today": len(expected),
        "present": len(present),
        "on_time": len(on_time),
        "late": len(late),
        "absent": len(expected - present),
        "pending_verification": len(pending),
        "attendance_rate": round(len(present & expected) / len(expected) * 100, 1) if expected else None,
        "average_lateness_min": round(sum(int(r["minutes_late"]) for r in late) / len(late), 1) if late else 0,
    }


async def dashboard(db, day: date, cal: rules.Calendar) -> dict:
    """Har xodim o'z grafigi bo'yicha: bugun ishlashi kerak bo'lganlar — ``scheduled_today``."""
    iso = day.isoformat()
    rows = await repo.events_between(db, iso, iso)
    ids = await repo.active_employee_ids(db)
    expected = set()
    for emp_id in ids:
        shift = rules.shift_from_row(await repo.employee_shift(db, emp_id, iso))
        if rules.is_required_day(shift, day, cal):
            expected.add(emp_id)
    out = _summary(rows, len(ids), expected)
    out["date"] = iso
    out["events"] = [_public_event(r) for r in rows]
    return out


async def events(db, start: date, end: date, employee_id: int | None = None,
                 status: str | None = None) -> list[dict]:
    rows = await repo.events_between(db, start.isoformat(), end.isoformat(), employee_id)
    return [_public_event(r) for r in rows if status is None or r["status"] == status]


_TZ = ZoneInfo("Asia/Tashkent")


def _public_event(r) -> dict:
    # Koordinatalar hisobotga chiqarilmaydi — faqat holat va vaqt (privacy by default).
    return {
        "id": r["id"], "employee_id": r["employee_id"], "employee_name": r["employee_name"],
        "kind": r["kind"], "work_date": r["work_date"], "server_ts": r["server_ts"],
        "local_time": datetime.fromisoformat(r["server_ts"]).astimezone(_TZ).strftime("%H:%M"),
        "status": r["status"], "minutes_late": r["minutes_late"], "minutes_early": r["minutes_early"],
    }
