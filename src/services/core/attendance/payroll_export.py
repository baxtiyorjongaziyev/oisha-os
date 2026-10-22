"""Hisobchi uchun faqat davomat faktlari; pul va jarima hisoblanmaydi."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.services.core.attendance import repo, summary
from src.services.core.attendance.service import AttendanceError

TZ = timezone(timedelta(hours=5))


async def period_payload(db, start: date, end: date, employee_id: int | None = None) -> dict:
    now = datetime.now(TZ)
    if end < start or (end - start).days > 365 or end > now.date():
        raise AttendanceError("invalid_range", 422)
    live = await repo.go_live_date(db)
    if not live:
        raise AttendanceError("attendance_not_configured", 503)
    rows = [] if end < date.fromisoformat(live) else await summary.period_summary(
        db, start, end, today=now.date(), employee_id=employee_id)
    incomplete = any(r["missing_check_out"] or r["pending_review"] for r in rows)
    return {
        "version": 1,
        "source": "attendance.period_summary",
        "informational_only": True,
        "timezone": "Asia/Tashkent",
        "generated_at": now.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "effective_start": max(start, date.fromisoformat(live)).isoformat(),
        "coverage": "before_go_live" if end < date.fromisoformat(live) else "available",
        "provisional": incomplete or end == now.date(),
        "rows": rows,
    }
