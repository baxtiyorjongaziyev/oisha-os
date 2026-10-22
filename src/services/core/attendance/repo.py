"""Smart Attendance SQL qatlami. Barcha so'rovlar parametrlangan."""
from __future__ import annotations

import json
from typing import Any


def _row(r) -> dict | None:
    if r is None:
        return None
    if isinstance(r, dict):
        return r
    if hasattr(r, "keys"):
        return {k: r[k] for k in r.keys()}
    return r  # SmartRow


async def one(db, sql: str, params: list[Any]) -> Any:
    rows = await db.execute(sql, params)
    return rows[0] if rows else None


async def employee_by_telegram(db, telegram_id: str):
    return await one(db, "SELECT id, name FROM employees WHERE telegram_id = ? AND is_active = 1",
                     [int(telegram_id)])


async def active_geofence(db, branch_id: int | None = None):
    sql = ("SELECT g.branch_id, g.latitude, g.longitude, g.radius_m, g.max_accuracy_m"
           " FROM geofences g JOIN attendance_branches b ON b.id = g.branch_id"
           " WHERE g.is_active = 1 AND b.is_active = 1")
    params: list[Any] = []
    if branch_id is not None:
        sql += " AND g.branch_id = ?"
        params.append(branch_id)
    return await one(db, sql + " ORDER BY g.id DESC LIMIT 1", params)


async def policy(db, branch_id: int):
    return await one(db, "SELECT grace_minutes, early_leave_grace_minutes, session_ttl_seconds,"
                         " qr_ttl_seconds FROM attendance_policies WHERE branch_id = ? OR branch_id IS NULL"
                         " ORDER BY branch_id IS NULL LIMIT 1", [branch_id])


async def session_by_idem(db, key: str):
    return await one(db, "SELECT * FROM attendance_sessions WHERE idempotency_key = ?", [key])


async def get_session(db, sid: str):
    return await one(db, "SELECT * FROM attendance_sessions WHERE id = ?", [sid])


async def confirmed_exists(db, employee_id: int, work_date: str, kind: str) -> bool:
    return bool(await one(db, "SELECT 1 FROM attendance_sessions WHERE employee_id = ? AND work_date = ?"
                              " AND kind = ? AND state = 'confirmed'", [employee_id, work_date, kind]))


async def insert_session(db, s: dict) -> None:
    await db.execute(
        "INSERT INTO attendance_sessions (id, employee_id, branch_id, kind, work_date, idempotency_key,"
        " expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [s["id"], s["employee_id"], s["branch_id"], s["kind"], s["work_date"], s["idempotency_key"],
         s["expires_at"]],
    )


async def advance(db, sid: str, employee_id: int, from_state: str, to_state: str, version: int,
                  extra_sql: str = "", extra: list[Any] | None = None) -> bool:
    """Optimistik o'tish: parallel so'rovlardan faqat bittasi holatni o'zgartiradi."""
    rows = await db.execute(
        f"UPDATE attendance_sessions SET state = ?, version = version + 1{extra_sql}"  # nosec B608 - extra_sql is a module constant
        " WHERE id = ? AND employee_id = ? AND state = ? AND version = ? RETURNING id",
        [to_state, *(extra or []), sid, employee_id, from_state, version],
    )
    return bool(rows)


async def add_verification(db, sid: str, method: str, passed: bool, score, reason: str, details: dict):
    await db.execute(
        "INSERT INTO attendance_verifications (session_id, method, passed, score, reason, details)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [sid, method, int(passed), score, reason, json.dumps(details, default=str)],
    )


async def verifications(db, sid: str) -> list:
    return await db.execute(
        "SELECT method, passed, reason, details FROM attendance_verifications WHERE session_id = ? ORDER BY id",
        [sid])


async def last_gps_fix(db, employee_id: int):
    return await one(db, "SELECT v.details FROM attendance_verifications v JOIN attendance_sessions s"
                         " ON s.id = v.session_id WHERE s.employee_id = ? AND v.method = 'gps'"
                         " ORDER BY v.id DESC LIMIT 1", [employee_id])


async def insert_event(db, e: dict) -> None:
    await db.execute(
        "INSERT INTO attendance_events (session_id, employee_id, branch_id, shift_id, kind, work_date,"
        " server_ts, status, minutes_late, minutes_early, verification_summary)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [e["session_id"], e["employee_id"], e["branch_id"], e.get("shift_id"), e["kind"], e["work_date"],
         e["server_ts"], e["status"], e["minutes_late"], e["minutes_early"],
         json.dumps(e["verification_summary"], default=str)],
    )


async def events_between(db, start: str, end: str, employee_id: int | None = None) -> list:
    sql = ("SELECT e.*, emp.name AS employee_name FROM attendance_events e"
           " JOIN employees emp ON emp.id = e.employee_id WHERE e.work_date BETWEEN ? AND ?")
    params: list[Any] = [start, end]
    if employee_id is not None:
        sql += " AND e.employee_id = ?"
        params.append(employee_id)
    return await db.execute(sql + " ORDER BY e.work_date, e.server_ts", params)


async def active_employee_count(db) -> int:
    r = await one(db, "SELECT COUNT(*) AS n FROM employees WHERE is_active = 1", [])
    return int(r[0] if r is not None else 0)
