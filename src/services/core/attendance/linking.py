"""Telegram hisobini xodimga bog'lash: xodim so'rov yuboradi, owner HR panelida tasdiqlaydi.

Mavjud ``employees`` yozuvining faqat ``telegram_id`` maydoni yangilanadi (bo'sh bo'lsa);
boshqa ma'lumotlar o'zgartirilmaydi va o'chirilmaydi.
"""
from __future__ import annotations

from src.services.core.attendance import audit, repo
from src.services.core.attendance.service import AttendanceError


async def request(db, *, telegram_id: int, full_name: str, ip: str | None = None) -> dict:
    name = " ".join((full_name or "").split())[:120]
    if len(name) < 2:
        raise AttendanceError("name_required", 422)
    if await repo.employee_by_telegram(db, str(telegram_id)) is not None:
        raise AttendanceError("already_linked", 409)
    rows = await db.execute(
        "INSERT INTO attendance_link_requests (telegram_id, full_name) VALUES (?, ?)"
        " ON CONFLICT (telegram_id) DO UPDATE SET full_name = excluded.full_name, state = 'pending',"
        " created_at = CURRENT_TIMESTAMP WHERE attendance_link_requests.state != 'linked' RETURNING id",
        [telegram_id, name])
    if not rows:
        raise AttendanceError("already_linked", 409)
    await audit.log(db, actor=str(telegram_id), action="link_requested", entity="link_request",
                    entity_id=rows[0][0], details={"name": name}, ip=ip)
    await db.commit()
    return {"id": int(rows[0][0]), "state": "pending", "name": name}


async def status(db, telegram_id: int) -> str | None:
    r = await repo.one(db, "SELECT state FROM attendance_link_requests WHERE telegram_id = ?", [telegram_id])
    return r[0] if r is not None else None


async def pending(db) -> list[dict]:
    rows = await db.execute("SELECT id, telegram_id, full_name, created_at FROM attendance_link_requests"
                            " WHERE state = 'pending' ORDER BY id", [])
    return [{"id": r["id"], "telegram_id": r["telegram_id"], "full_name": r["full_name"],
             "created_at": r["created_at"]} for r in rows]


async def approve(db, *, actor: str, request_id: int, employee_id: int | None = None,
                  ip: str | None = None) -> dict:
    req = await repo.one(db, "SELECT telegram_id, full_name, state FROM attendance_link_requests WHERE id = ?",
                         [request_id])
    if req is None or req["state"] != "pending":
        raise AttendanceError("request_not_found", 404)
    tg, name = int(req["telegram_id"]), str(req["full_name"])
    if await repo.employee_by_telegram(db, str(tg)) is not None:
        raise AttendanceError("already_linked", 409)
    if employee_id is None:
        rows = await db.execute("INSERT INTO employees (telegram_id, name, role) VALUES (?, ?, 'xodim') RETURNING id",
                                [tg, name])
        employee_id = int(rows[0][0])
        created = True
    else:
        rows = await db.execute("UPDATE employees SET telegram_id = ? WHERE id = ? AND is_active = 1"
                                " AND telegram_id IS NULL RETURNING id", [tg, employee_id])
        if not rows:
            raise AttendanceError("employee_not_linkable", 409)
        created = False
    await db.execute("UPDATE attendance_link_requests SET state = 'linked', employee_id = ?, resolved_by = ?,"
                     " resolved_at = CURRENT_TIMESTAMP WHERE id = ?", [employee_id, actor, request_id])
    await audit.log(db, actor=actor, action="employee_linked", entity="employee", entity_id=employee_id,
                    details={"telegram_id": tg, "request_id": request_id, "created": created}, ip=ip)
    await db.commit()
    return {"employee_id": employee_id, "created": created}


async def reject(db, *, actor: str, request_id: int, ip: str | None = None) -> None:
    rows = await db.execute("UPDATE attendance_link_requests SET state = 'rejected', resolved_by = ?,"
                            " resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND state = 'pending' RETURNING id",
                            [actor, request_id])
    if not rows:
        raise AttendanceError("request_not_found", 404)
    await audit.log(db, actor=actor, action="link_rejected", entity="link_request", entity_id=request_id, ip=ip)
    await db.commit()


async def unlinked_employees(db) -> list[dict]:
    rows = await db.execute("SELECT id, name FROM employees WHERE is_active = 1 AND telegram_id IS NULL"
                            " ORDER BY name", [])
    return [{"id": r["id"], "name": r["name"]} for r in rows]
