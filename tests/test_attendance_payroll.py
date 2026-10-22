"""Synthetic SQLite attendance facts exposed to Hisobchi through a scoped API."""
from datetime import datetime

from src.api.rbac import Principal, Role
from test_attendance_flow import TZ5, _full, client, env, run  # noqa: F401

URL = "/api/attendance/payroll/summary?start=2026-10-22&end=2026-10-22"


def test_payroll_permission_boundary(client):
    c, state = client
    assert c.get(URL).status_code == 403
    state["principal"] = Principal("hisobchi", Role.SERVICE, "service", scopes=frozenset({"finance:read"}))
    assert c.get(URL).status_code == 403
    state["principal"] = Principal("hisobchi", Role.SERVICE, "service", scopes=frozenset({"attendance:read:all"}))
    assert c.get(URL).status_code == 200


def test_payroll_exposes_facts_without_salary(client, env):
    c, state = client
    db, svc, clock, _ = env
    db.conn.execute("UPDATE geofences SET created_at = '2026-10-01 00:00:00'")
    clock.t = datetime(2026, 10, 22, 10, 30, tzinfo=TZ5)
    _full(svc, db, clock, key="synthetic-payroll-in")
    clock.t = datetime(2026, 10, 22, 19, 30, tzinfo=TZ5)
    _full(svc, db, clock, kind="check_out", key="synthetic-payroll-out")
    state["principal"] = Principal("owner", Role.OWNER, "session")
    response = c.get(URL + "&employee_id=1")
    assert response.status_code == 200
    data = response.json()
    assert data["informational_only"] is True
    assert data["timezone"] == "Asia/Tashkent"
    assert data["source"] == "attendance.period_summary"
    row = data["rows"][0]
    assert row["worked_minutes"] == 540 and row["worked_hours"] == 9
    assert row["overtime_minutes"] == 30 and row["late_minutes"] == 30
    assert row["early_leave_minutes"] == 0 and row["approved_leave_days"] == 0
    assert not {"salary", "fine", "deduction", "base_salary", "telegram_id"}.intersection(row)
    assert response.headers["cache-control"] == "no-store"
    assert db.conn.execute("SELECT COUNT(*) FROM attendance_audit_logs WHERE action='payroll_summary_viewed'").fetchone()[0] == 1


def test_payroll_invalid_period_and_no_config_are_explicit(client, env):
    c, state = client
    state["principal"] = Principal("owner", Role.OWNER, "session")
    assert c.get("/api/attendance/payroll/summary?start=2026-10-23&end=2026-10-22").status_code == 422
    assert c.get("/api/attendance/payroll/summary?start=2099-01-01&end=2099-01-02").status_code == 422
    assert c.get(URL + "&employee_id=-1").status_code == 422
    db, _, _, _ = env
    db.conn.execute("DELETE FROM geofences")
    assert c.get(URL).status_code == 503
