"""Smart Attendance end-to-end: servis + API (in-memory SQLite, tarmoqsiz)."""
import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Principal, Role
from src.api.routes import attendance_routes as routes
from src.services.core.attendance import admin, qr_tokens as qr
from src.services.core.attendance.geofence import LocationFix
from src.services.core.attendance.schema import init_attendance_tables
from src.services.core.attendance.service import Actor, AttendanceError, AttendanceService

SECRET = "q" * 40
LAT, LON = 40.4710, 71.7240
TZ5 = timezone(timedelta(hours=5))
THU_0955 = datetime(2026, 10, 22, 9, 55, tzinfo=TZ5)


class SqliteDb:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE,"
                          " name TEXT, role TEXT, is_active INTEGER DEFAULT 1)")
        self.conn.executemany("INSERT INTO employees VALUES (?, ?, ?, 'designer', 1)",
                              [(1, 111, "Ali"), (2, 222, "Vali")])

    async def execute(self, q, p=None):
        return self.conn.execute(q, p or []).fetchall()

    async def commit(self):
        self.conn.commit()

    async def rollback(self):
        self.conn.rollback()


class FakeNotifier:
    def __init__(self):
        self.sent = []

    async def notify_review(self, text):
        self.sent.append(text)
        return True


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def env():
    db = SqliteDb()
    run(init_attendance_tables(db))
    run(admin.configure_office(db, actor="owner", name="Bosh ofis", latitude=LAT, longitude=LON,
                               radius_m=100, max_accuracy_m=50))
    clock = Clock(THU_0955)
    notifier = FakeNotifier()
    svc = AttendanceService(db, clock=clock, notifier=notifier, qr_secret=SECRET)
    return db, svc, clock, notifier


ALI = Actor(1, "Ali", "111")
VALI = Actor(2, "Vali", "222")


def _qr(db, clock):
    token, claims = qr.issue(1, "kiosk", clock(), secret=SECRET)
    run(qr.record_issued(db, claims))
    return token


def _fix(clock, lat=LAT, acc=10.0, mocked=None):
    return LocationFix(lat, LON, acc, clock(), mocked)


def _full(svc, db, clock, actor=ALI, kind="check_in", key="key-aaaaaaa1", **fix_kw):
    s = run(svc.start(actor, kind, key))
    run(svc.submit_location(s["id"], actor, _fix(clock, **fix_kw)))
    run(svc.submit_qr(s["id"], actor, _qr(db, clock)))
    return s, run(svc.confirm(s["id"], actor))


def test_happy_path_on_time(env):
    db, svc, clock, notifier = env
    _, res = _full(svc, db, clock)
    assert res["status"] == "ON_TIME" and notifier.sent == []


def test_late_then_checkout_early(env):
    db, svc, clock, _ = env
    clock.t = datetime(2026, 10, 22, 10, 30, tzinfo=TZ5)
    _, res = _full(svc, db, clock)
    assert res["status"] == "LATE" and res["minutes_late"] == 30
    clock.t = datetime(2026, 10, 22, 18, 0, tzinfo=TZ5)
    _, out = _full(svc, db, clock, kind="check_out", key="key-aaaaaaa2")
    assert out["status"] == "EARLY_LEAVE" and out["minutes_early"] == 60


def test_outside_geofence_rejected(env):
    db, svc, clock, _ = env
    s = run(svc.start(ALI, "check_in", "key-out-0001"))
    with pytest.raises(AttendanceError) as e:
        run(svc.submit_location(s["id"], ALI, _fix(clock, lat=40.49)))
    assert e.value.code == "outside_geofence"
    with pytest.raises(AttendanceError):
        run(svc.confirm(s["id"], ALI))  # GPS/QR siz tasdiqlanmaydi


def test_low_accuracy_goes_to_review_and_notifies_owner(env):
    db, svc, clock, notifier = env
    _, res = _full(svc, db, clock, acc=300)
    assert res["status"] == "PENDING_REVIEW"
    assert len(notifier.sent) == 1 and "Ali" in notifier.sent[0]


def test_mocked_gps_goes_to_review(env):
    db, svc, clock, _ = env
    _, res = _full(svc, db, clock, mocked=True)
    assert res["status"] == "PENDING_REVIEW"


def test_expired_qr(env):
    db, svc, clock, _ = env
    s = run(svc.start(ALI, "check_in", "key-exp-0001"))
    run(svc.submit_location(s["id"], ALI, _fix(clock)))
    token = _qr(db, clock)
    clock.t += timedelta(seconds=60)
    with pytest.raises(AttendanceError) as e:
        run(svc.submit_qr(s["id"], ALI, token))
    assert e.value.code == "qr_expired"


def test_qr_replay_same_employee(env):
    db, svc, clock, _ = env
    token = _qr(db, clock)
    s1 = run(svc.start(ALI, "check_in", "key-rep-0001"))
    run(svc.submit_location(s1["id"], ALI, _fix(clock)))
    run(svc.submit_qr(s1["id"], ALI, token))
    s2 = run(svc.start(ALI, "check_in", "key-rep-0002"))
    run(svc.submit_location(s2["id"], ALI, _fix(clock)))
    with pytest.raises(AttendanceError) as e:
        run(svc.submit_qr(s2["id"], ALI, token))
    assert e.value.code == "qr_replayed"


def test_duplicate_check_in_blocked(env):
    db, svc, clock, _ = env
    _full(svc, db, clock)
    with pytest.raises(AttendanceError) as e:
        run(svc.start(ALI, "check_in", "key-dup-0002"))
    assert e.value.code == "already_recorded"


def test_parallel_confirm_only_one_event(env):
    db, svc, clock, _ = env
    sessions = []
    for i in range(2):  # ikkala sessiya duplicate tekshiruvdan oldin ochilgan
        s = run(svc.start(ALI, "check_in", f"key-par-000{i}"))
        run(svc.submit_location(s["id"], ALI, _fix(clock)))
        run(svc.submit_qr(s["id"], ALI, _qr(db, clock)))
        sessions.append(s)
    run(svc.confirm(sessions[0]["id"], ALI))
    with pytest.raises(AttendanceError) as e:
        run(svc.confirm(sessions[1]["id"], ALI))
    assert e.value.code == "already_recorded"
    assert db.conn.execute("SELECT COUNT(*) FROM attendance_events").fetchone()[0] == 1


def test_idempotent_start_returns_same_session(env):
    _, svc, _, _ = env
    a = run(svc.start(ALI, "check_in", "key-idem-001"))
    b = run(svc.start(ALI, "check_in", "key-idem-001"))
    assert a["id"] == b["id"]
    with pytest.raises(AttendanceError):
        run(svc.start(VALI, "check_in", "key-idem-001"))


def test_other_employee_cannot_touch_session(env):
    db, svc, clock, _ = env
    s = run(svc.start(ALI, "check_in", "key-own-0001"))
    with pytest.raises(AttendanceError) as e:
        run(svc.submit_location(s["id"], VALI, _fix(clock)))
    assert e.value.status == 404


def test_checkout_requires_check_in(env):
    _, svc, _, _ = env
    with pytest.raises(AttendanceError) as e:
        run(svc.start(ALI, "check_out", "key-co-00001"))
    assert e.value.code == "check_in_required"


def test_face_step_disabled(env):
    _, svc, _, _ = env
    s = run(svc.start(ALI, "check_in", "key-face-001"))
    with pytest.raises(AttendanceError) as e:
        run(svc.submit_face(s["id"], ALI))
    assert e.value.status == 501


def test_hr_correction_audited(env):
    db, svc, clock, _ = env
    clock.t = datetime(2026, 10, 22, 10, 40, tzinfo=TZ5)
    _full(svc, db, clock)
    ev = db.conn.execute("SELECT id, status FROM attendance_events").fetchone()
    assert ev["status"] == "LATE"
    res = run(admin.apply_correction(db, actor="owner", employee_id=1, work_date="2026-10-22",
                                     new_status="ON_TIME", reason="Mijoz uchrashuvida edi", event_id=ev["id"]))
    assert res["old_status"] == "LATE"
    assert db.conn.execute("SELECT status FROM attendance_events").fetchone()[0] == "ON_TIME"
    actions = [r[0] for r in db.conn.execute("SELECT action FROM attendance_audit_logs")]
    assert "correction_applied" in actions
    with pytest.raises(AttendanceError):
        run(admin.apply_correction(db, actor="owner", employee_id=1, work_date="2026-10-22",
                                   new_status="HACKED", reason="xxxxxxx", event_id=ev["id"]))


def test_no_geofence_fails_closed():
    db = SqliteDb()
    run(init_attendance_tables(db))
    svc = AttendanceService(db, qr_secret=SECRET)
    with pytest.raises(AttendanceError) as e:
        run(svc.start(ALI, "check_in", "key-nogeo-01"))
    assert e.value.status == 503


# ---- API qatlami ----
@pytest.fixture
def client(env, monkeypatch):
    db, _, _, _ = env
    monkeypatch.setattr(routes, "_db", lambda: db)
    monkeypatch.setattr(routes, "_schema_ready", True)
    monkeypatch.setattr(routes, "default_notifier", lambda: FakeNotifier())
    monkeypatch.setenv("ATTENDANCE_QR_SECRET", SECRET)
    routes._limiter.hits.clear()
    app = FastAPI()
    app.include_router(routes.router)
    state = {"principal": Principal("111", Role.VIEWER, "session")}
    for dep in (routes._SELF, routes._READ_ALL, routes._MANAGE, routes._KIOSK):
        real = dep.dependency

        async def override(request: routes.Request, _real=real):
            from src.api.rbac import has_permission
            p = state["principal"]
            needed = _real.__oisha_permissions__
            mode = _real.__oisha_permission_mode__
            checks = [has_permission(p, routes.Permission(x)) for x in needed]
            if not (all(checks) if mode == "all" else any(checks)):
                raise routes.HTTPException(status_code=403, detail="Forbidden")
            return p
        app.dependency_overrides[real] = override
    return TestClient(app), state


def test_api_employee_flow_and_rbac(client):
    c, state = client
    r = c.post("/api/attendance/sessions", json={"kind": "check_in"}, headers={"Idempotency-Key": "api-key-0001"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    now = datetime.now(timezone.utc).isoformat()
    r = c.post(f"/api/attendance/sessions/{sid}/location",
               json={"latitude": LAT, "longitude": LON, "accuracy_m": 10, "captured_at": now})
    assert r.status_code == 200, r.text
    # xodim QR chiqara olmaydi va admin dashboard ko'ra olmaydi
    assert c.get("/api/attendance/kiosk/qr").status_code == 403
    assert c.get("/api/attendance/admin/dashboard").status_code == 403
    state["principal"] = Principal("owner", Role.OWNER, "session")
    token = c.get("/api/attendance/kiosk/qr").json()["token"]
    state["principal"] = Principal("111", Role.VIEWER, "session")
    assert c.post(f"/api/attendance/sessions/{sid}/qr", json={"token": token}).status_code == 200
    r = c.post(f"/api/attendance/sessions/{sid}/confirm")
    assert r.status_code == 200 and r.json()["status"] in {"ON_TIME", "LATE", "PENDING_REVIEW"}
    assert len(c.get("/api/attendance/today").json()["events"]) <= 1
    state["principal"] = Principal("owner", Role.OWNER, "session")
    dash = c.get("/api/attendance/admin/dashboard").json()
    assert dash["total_employees"] == 2


def test_api_unknown_telegram_user_forbidden(client):
    c, state = client
    state["principal"] = Principal("999", Role.VIEWER, "session")
    r = c.post("/api/attendance/sessions", json={"kind": "check_in"}, headers={"Idempotency-Key": "api-key-0002"})
    assert r.status_code == 403 and r.json()["detail"] == "not_an_employee"


def test_api_validation_and_rate_limit(client):
    c, _ = client
    bad = c.post("/api/attendance/sessions", json={"kind": "teleport"}, headers={"Idempotency-Key": "api-key-0003"})
    assert bad.status_code == 422
    codes = [c.get("/api/attendance/today").status_code for _ in range(35)]
    assert 429 in codes


def test_personal_schedule_drives_status_and_dashboard(env):
    db, _, clock, _ = env
    svc = AttendanceService(db, clock=clock, notifier=FakeNotifier(), qr_secret=SECRET)  # bazadagi grafik
    wed = datetime(2026, 10, 21, 10, 0, tzinfo=TZ5)
    run(admin.set_schedule(db, actor="owner", employee_id=1, weekdays=[1, 2, 4, 5, 6, 7],
                           valid_from="2026-10-01"))
    clock.t = wed
    _, res = _full(svc, db, clock)  # Ali chorshanba dam oladi, lekin keldi
    assert res["status"] == "PENDING_REVIEW"
    from src.services.core.attendance import reports, rules
    dash = run(reports.dashboard(db, wed.date(), rules.Calendar()))
    assert dash["scheduled_today"] == 1 and dash["absent"] == 1  # faqat Vali kutilgan edi
    with pytest.raises(ValueError):
        run(admin.set_schedule(db, actor="owner", employee_id=1, weekdays=[8], valid_from="2026-10-01"))
