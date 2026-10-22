"""HR dashboard ko'rsatkichlari va hisobot qatorlari (faqat o'qish)."""
from __future__ import annotations

from datetime import date

from src.services.core.attendance import repo, rules


def _summary(rows: list, total: int, working_day: bool) -> dict:
    check_ins = [r for r in rows if r["kind"] == "check_in"]
    present = {int(r["employee_id"]) for r in check_ins}
    late = [r for r in check_ins if r["status"] == rules.LATE]
    on_time = [r for r in check_ins if r["status"] == rules.ON_TIME]
    pending = [r for r in rows if r["status"] == rules.PENDING_REVIEW]
    absent = max(0, total - len(present)) if working_day else 0
    return {
        "total_employees": total,
        "present": len(present),
        "on_time": len(on_time),
        "late": len(late),
        "absent": absent,
        "pending_verification": len(pending),
        "attendance_rate": round(len(present) / total * 100, 1) if total and working_day else None,
        "average_lateness_min": round(sum(int(r["minutes_late"]) for r in late) / len(late), 1) if late else 0,
        "working_day": working_day,
    }


async def dashboard(db, day: date, shift: rules.Shift, cal: rules.Calendar) -> dict:
    iso = day.isoformat()
    rows = await repo.events_between(db, iso, iso)
    total = await repo.active_employee_count(db)
    out = _summary(rows, total, rules.is_working_day(shift, day, cal))
    out["date"] = iso
    out["events"] = [_public_event(r) for r in rows]
    return out


async def events(db, start: date, end: date, employee_id: int | None = None) -> list[dict]:
    rows = await repo.events_between(db, start.isoformat(), end.isoformat(), employee_id)
    return [_public_event(r) for r in rows]


def _public_event(r) -> dict:
    # Koordinatalar hisobotga chiqarilmaydi — faqat holat va vaqt (privacy by default).
    return {
        "id": r["id"], "employee_id": r["employee_id"], "employee_name": r["employee_name"],
        "kind": r["kind"], "work_date": r["work_date"], "server_ts": r["server_ts"],
        "status": r["status"], "minutes_late": r["minutes_late"], "minutes_early": r["minutes_early"],
    }
