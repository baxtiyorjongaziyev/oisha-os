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
    from src.api.routes import attendance_setup_routes as setup
    app.include_router(setup.router)
    for dep in (routes._SELF, routes._READ_ALL, routes._MANAGE, setup._SELF, setup._MANAGE):
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
    assert c.get("/api/attendance/kiosk/qr").status_code == 401
    assert c.get("/api/attendance/admin/dashboard").status_code == 403
    assert c.post("/api/attendance/admin/kiosk-tokens", json={}).status_code == 403
    state["principal"] = Principal("owner", Role.OWNER, "session")
    kiosk_token = c.post("/api/attendance/admin/kiosk-tokens", json={"label": "Ofis"}).json()["token"]
    assert c.get("/api/attendance/kiosk/qr", headers={"Authorization": "Bearer oak_wrong"}).status_code == 401
    token = c.get("/api/attendance/kiosk/qr", headers={"Authorization": f"Bearer {kiosk_token}"}).json()["token"]
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


def test_optional_day_schedule_roundtrip(env):
    db, _, clock, _ = env
    res = run(admin.set_schedule(db, actor="owner", employee_id=2, weekdays=[1, 2, 3, 4, 5, 6, 7],
                                 optional_weekdays=[7], valid_from="2026-10-01"))
    assert res["weekdays"] == [1, 2, 3, 4, 5, 6] and res["optional_weekdays"] == [7]
    from src.services.core.attendance import reports, rules
    sun = datetime(2026, 10, 25, 10, 0, tzinfo=TZ5).date()
    dash = run(reports.dashboard(db, sun, rules.Calendar()))
    assert dash["scheduled_today"] == 0  # Ali — yakshanba dam, Vali — ixtiyoriy


def test_schedule_config_is_valid():
    from src.services.core.attendance.team_schedules import TEAM_SCHEDULES
    for item in TEAM_SCHEDULES:
        assert set(item["weekdays"]) <= set(range(1, 8))
        assert set(item.get("optional_weekdays", [])) <= set(range(1, 8))


def test_pages_served_with_privacy_headers():
    app = FastAPI()
    app.include_router(routes.pages_router)
    c = TestClient(app)
    for path in routes.PAGES:
        r = c.get(path)
        assert r.status_code == 200 and r.headers["x-content-type-options"] == "nosniff"
        assert "geolocation=(self)" in r.headers["permissions-policy"]
        assert r.headers["x-frame-options"] == "DENY"
    assert "/static/" not in c.get("/api/attendance/app").text


def test_only_page_shells_are_public():
    from src.api.security import is_protected_path
    for path in routes.PAGES:
        assert not is_protected_path(path), path
    assert not is_protected_path("/api/attendance/kiosk/qr")  # route ichida kiosk kaliti tekshiriladi
    for path in ("/api/attendance/today", "/api/attendance/admin/reports", "/api/attendance/admin/kiosk-tokens",
                 "/api/attendance/app/../admin/dashboard", "/api/attendance/app/x"):
        assert is_protected_path(path), path


def test_login_redirect_whitelist_includes_attendance_only():
    from src.services.api_server.oauth import _safe_login_next, _safe_redirect_target
    assert _safe_redirect_target("/api/attendance/app") == "/api/attendance/app"
    assert _safe_login_next("/api/attendance/app/admin") == "/api/attendance/app/admin"
    assert _safe_redirect_target("/api/attendance/app/../evil") == "/"
    assert _safe_login_next("https://evil.example/api/attendance/app") == ""


def test_office_constant_matches_owner_input():
    from src.services.core.attendance.team_schedules import OFFICE
    assert (OFFICE["latitude"], OFFICE["longitude"]) == (41.3056580, 69.2814659)


def test_kiosk_token_revocation(client):
    c, state = client
    state["principal"] = Principal("owner", Role.OWNER, "session")
    tok = c.post("/api/attendance/admin/kiosk-tokens", json={}).json()["token"]
    auth = {"Authorization": f"Bearer {tok}"}
    assert c.get("/api/attendance/kiosk/qr", headers=auth).status_code == 200
    tid = c.get("/api/attendance/admin/kiosk-tokens").json()["tokens"][0]["id"]
    assert c.delete(f"/api/attendance/admin/kiosk-tokens/{tid}").status_code == 200
    assert c.get("/api/attendance/kiosk/qr", headers=auth).status_code == 401


def test_link_request_flow(client):
    c, state = client
    state["principal"] = Principal("555", Role.VIEWER, "session")
    assert c.post("/api/attendance/sessions", json={"kind": "check_in"},
                  headers={"Idempotency-Key": "link-key-001"}).status_code == 403
    r = c.post("/api/attendance/link-request", json={"full_name": "Mumtozmaxal Karimova"})
    assert r.status_code == 200 and c.get("/api/attendance/link-request").json()["state"] == "pending"
    state["principal"] = Principal("owner", Role.OWNER, "session")
    reqs = c.get("/api/attendance/admin/link-requests").json()
    assert reqs["requests"][0]["full_name"] == "Mumtozmaxal Karimova"
    res = c.post(f"/api/attendance/admin/link-requests/{reqs['requests'][0]['id']}/approve", json={}).json()
    assert res["created"] is True
    state["principal"] = Principal("555", Role.VIEWER, "session")
    assert c.post("/api/attendance/sessions", json={"kind": "check_in"},
                  headers={"Idempotency-Key": "link-key-002"}).status_code == 200
    # owner bergan grafik avtomatik qo'llandi (chorshanba dam, yakshanba ish)
    state["principal"] = Principal("owner", Role.OWNER, "session")
    emps = {e["name"]: e for e in c.get("/api/attendance/admin/employees").json()["employees"]}
    assert emps["Mumtozmaxal Karimova"]["weekdays"] == [1, 2, 4, 5, 6, 7]
    assert c.post("/api/attendance/link-request", json={"full_name": "x"}).status_code == 422


def test_link_to_existing_employee_and_no_overwrite(env):
    db, _, _, _ = env
    from src.services.core.attendance import linking
    db.conn.execute("INSERT INTO employees (id, telegram_id, name, role, is_active) VALUES (3, NULL, 'Ahror', 'x', 1)")
    req = run(linking.request(db, telegram_id=777, full_name="Ahror"))
    assert run(linking.unlinked_employees(db)) == [{"id": 3, "name": "Ahror"}]
    run(linking.approve(db, actor="owner", request_id=req["id"], employee_id=3))
    assert db.conn.execute("SELECT telegram_id FROM employees WHERE id = 3").fetchone()[0] == 777
    req2 = run(linking.request(db, telegram_id=888, full_name="Boshqa"))
    with pytest.raises(AttendanceError):  # Ali (id=1) allaqachon bog'langan — ustidan yozilmaydi
        run(linking.approve(db, actor="owner", request_id=req2["id"], employee_id=1))


def test_bootstrap_fills_only_missing(env):
    db, _, _, _ = env
    from src.services.core.attendance import bootstrap
    db.conn.execute("INSERT INTO employees (id, telegram_id, name, role, is_active) VALUES (4, 444, 'Hasanboy', 'x', 1)")
    rep = run(bootstrap.run(db))
    assert rep["office"] == "exists" and rep["schedules"] == ["Hasanboy"]
    assert run(bootstrap.run(db))["schedules"] == []  # ikkinchi marta — hech narsa o'zgarmaydi


def test_bootstrap_creates_office_when_missing():
    db = SqliteDb()
    run(init_attendance_tables(db))
    from src.services.core.attendance import bootstrap, repo
    assert run(bootstrap.run(db))["office"] == "created"
    fence = run(repo.active_geofence(db))
    assert (fence["latitude"], fence["longitude"], fence["radius_m"]) == (41.305658, 69.2814659, 150)


def test_qr_secret_derived_without_env(monkeypatch):
    from src.services.core.attendance import secrets_util
    monkeypatch.delenv("ATTENDANCE_QR_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "j" * 40)
    derived = secrets_util.qr_secret()
    assert len(derived) == 64 and "j" * 10 not in derived
    monkeypatch.setenv("ATTENDANCE_QR_SECRET", "e" * 40)
    assert secrets_util.qr_secret() == "e" * 40  # aniq berilgan kalit ustun
