"""HR amallari: ofis/geofence sozlash va qo'lda tuzatish. Har amal audit qilinadi."""
from __future__ import annotations

from src.services.core.attendance import audit, repo, rules
from src.services.core.attendance.service import AttendanceError

_STATUSES = frozenset(rules.__dict__[n] for n in (
    "ON_TIME", "LATE", "EARLY_LEAVE", "ABSENT", "APPROVED_LEAVE", "DAY_OFF", "PENDING_REVIEW"))


async def configure_office(db, *, actor: str, name: str, latitude: float, longitude: float,
                           radius_m: int, max_accuracy_m: int, ip: str | None = None) -> dict:
    """Bitta ofis (owner, 2026-10-22). Eski geofence o'chiriladi, yangisi faollashadi."""
    branch = await repo.one(db, "SELECT id FROM attendance_branches ORDER BY id LIMIT 1", [])
    if branch is None:
        rows = await db.execute("INSERT INTO attendance_branches (name) VALUES (?) RETURNING id", [name])
        branch_id = int(rows[0][0])
    else:
        branch_id = int(branch[0])
        await db.execute("UPDATE attendance_branches SET name = ?, is_active = 1 WHERE id = ?", [name, branch_id])
    await db.execute("UPDATE geofences SET is_active = 0 WHERE branch_id = ?", [branch_id])
    await db.execute(
        "INSERT INTO geofences (branch_id, latitude, longitude, radius_m, max_accuracy_m) VALUES (?, ?, ?, ?, ?)",
        [branch_id, latitude, longitude, radius_m, max_accuracy_m],
    )
    await audit.log(db, actor=actor, action="office_configured", entity="attendance_branch",
                    entity_id=branch_id, details={"radius_m": radius_m, "max_accuracy_m": max_accuracy_m}, ip=ip)
    await db.commit()
    return {"branch_id": branch_id}


async def apply_correction(db, *, actor: str, employee_id: int, work_date: str, new_status: str,
                           reason: str, event_id: int | None = None, ip: str | None = None) -> dict:
    if new_status not in _STATUSES:
        raise AttendanceError("invalid_status", 422)
    if len((reason or "").strip()) < 5:
        raise AttendanceError("reason_required", 422)
    old_status = None
    if event_id is not None:
        ev = await repo.one(db, "SELECT status FROM attendance_events WHERE id = ? AND employee_id = ?",
                            [event_id, employee_id])
        if ev is None:
            raise AttendanceError("event_not_found", 404)
        old_status = ev[0]
        await db.execute("UPDATE attendance_events SET status = ? WHERE id = ?", [new_status, event_id])
    rows = await db.execute(
        "INSERT INTO attendance_corrections (employee_id, work_date, event_id, new_status, reason, requested_by,"
        " approved_by, state) VALUES (?, ?, ?, ?, ?, ?, ?, 'applied') RETURNING id",
        [employee_id, work_date, event_id, new_status, reason.strip(), actor, actor],
    )
    correction_id = int(rows[0][0])
    await audit.log(db, actor=actor, action="correction_applied", entity="attendance_correction",
                    entity_id=correction_id, ip=ip,
                    details={"event_id": event_id, "old": old_status, "new": new_status, "reason": reason})
    await db.commit()
    return {"id": correction_id, "old_status": old_status, "new_status": new_status}
