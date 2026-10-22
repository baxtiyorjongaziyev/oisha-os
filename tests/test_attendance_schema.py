"""Smart Attendance sxemasi: idempotentlik va himoya cheklovlari (in-memory SQLite)."""
import asyncio
import sqlite3

import pytest

from src.services.core.attendance.schema import init_attendance_tables


class _SqliteDb:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL)"
        )
        self.conn.execute("INSERT INTO employees (id, name, role) VALUES (1, 'Test Xodim', 'designer')")

    async def execute(self, query, params=None):
        return self.conn.execute(query, params or []).fetchall()

    async def commit(self):
        self.conn.commit()


@pytest.fixture
def db():
    d = _SqliteDb()
    asyncio.run(init_attendance_tables(d))
    asyncio.run(init_attendance_tables(d))  # ikkinchi marta — idempotent
    d.conn.execute("INSERT INTO attendance_branches (id, name) VALUES (1, 'Bosh ofis')")
    return d


def _session(db, sid, state="created", key=None):
    db.conn.execute(
        "INSERT INTO attendance_sessions (id, employee_id, branch_id, kind, work_date, state,"
        " idempotency_key, expires_at) VALUES (?, 1, 1, 'check_in', '2026-10-22', ?, ?, 'x')",
        [sid, state, key],
    )


def test_only_one_confirmed_check_in_per_day(db):
    _session(db, "a", state="rejected")
    _session(db, "b", state="confirmed")
    with pytest.raises(sqlite3.IntegrityError):
        _session(db, "c", state="confirmed")


def test_idempotency_key_unique(db):
    _session(db, "a", key="k1")
    with pytest.raises(sqlite3.IntegrityError):
        _session(db, "b", key="k1")


def test_qr_nonce_cannot_repeat(db):
    sql = ("INSERT INTO qr_challenges (branch_id, nonce, kiosk_id, issued_at, expires_at)"
           " VALUES (1, 'n1', 'kiosk', 't', 't')")
    db.conn.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(sql)


def test_audit_log_is_append_only(db):
    db.conn.execute("INSERT INTO attendance_audit_logs (actor, action, entity) VALUES ('u', 'a', 'e')")
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute("UPDATE attendance_audit_logs SET actor = 'x'")
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute("DELETE FROM attendance_audit_logs")


def test_unknown_employee_rejected_by_fk(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO face_enrollments (employee_id, provider, consent_version, consent_at)"
            " VALUES (999, 'disabled', 'v1', 't')"
        )


def test_invalid_geofence_radius_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO geofences (branch_id, latitude, longitude, radius_m) VALUES (1, 40.4, 71.7, 1)"
        )


def test_correction_requires_reason(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO attendance_corrections (employee_id, work_date, new_status, reason, requested_by)"
            " VALUES (1, '2026-10-22', 'ON_TIME', 'ok', 'hr')"
        )
