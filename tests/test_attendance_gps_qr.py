"""GPS geofence va dinamik QR testlari (tarmoqsiz, in-memory SQLite)."""
import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.services.core.attendance import geofence as gf
from src.services.core.attendance import qr_tokens as qr
from src.services.core.attendance.schema import init_attendance_tables

NOW = datetime(2026, 10, 22, 8, 55, tzinfo=timezone.utc)
OFFICE = gf.Geofence(latitude=40.4710, longitude=71.7240, radius_m=100, max_accuracy_m=50)
SECRET = "s" * 40


def _fix(lat=40.4710, lon=71.7240, acc=10.0, at=NOW, mocked=None):
    return gf.LocationFix(lat, lon, acc, at, mocked)


# ---- GPS ----

def test_inside_office_passes():
    r = gf.evaluate(OFFICE, _fix(), NOW)
    assert r.passed and r.reasons == []


def test_outside_geofence_fails():
    r = gf.evaluate(OFFICE, _fix(lat=40.4800), NOW)  # ~1 km
    assert not r.passed and "outside_geofence" in r.reasons


def test_low_accuracy_fails_and_needs_review():
    r = gf.evaluate(OFFICE, _fix(acc=300), NOW)
    assert not r.passed and "low_accuracy" in r.reasons and r.needs_review


def test_accuracy_circle_must_fit_inside_fence():
    # markazdan ~90 m, aniqlik 40 m => 130 m > 100 m radius
    r = gf.evaluate(OFFICE, _fix(lat=40.47181, acc=40), NOW)
    assert not r.passed


def test_stale_timestamp_fails():
    r = gf.evaluate(OFFICE, _fix(at=NOW - timedelta(minutes=10)), NOW)
    assert "stale_or_future_timestamp" in r.reasons and not r.passed


def test_mock_location_flag_blocks():
    r = gf.evaluate(OFFICE, _fix(mocked=True), NOW)
    assert not r.passed and r.needs_review and "mock_location_flag" in r.reasons


def test_impossible_travel_flags():
    prev = gf.PreviousFix(41.3111, 69.2797, NOW - timedelta(minutes=5))  # Toshkent, 5 daqiqa oldin
    r = gf.evaluate(OFFICE, _fix(), NOW, previous=prev)
    assert "impossible_travel" in r.reasons and not r.passed


def test_invalid_coordinates():
    assert not gf.evaluate(OFFICE, _fix(lat=200), NOW).passed


# ---- QR ----

def test_qr_roundtrip():
    token, claims = qr.issue(1, "kiosk-1", NOW, secret=SECRET)
    assert qr.verify(token, 1, NOW + timedelta(seconds=10), secret=SECRET).nonce == claims.nonce


def test_qr_expired():
    token, _ = qr.issue(1, "kiosk-1", NOW, secret=SECRET)
    with pytest.raises(qr.QrError) as e:
        qr.verify(token, 1, NOW + timedelta(seconds=40), secret=SECRET)
    assert e.value.code == "expired"


def test_qr_tampered_signature():
    token, _ = qr.issue(1, "kiosk-1", NOW, secret=SECRET)
    with pytest.raises(qr.QrError) as e:
        qr.verify(token, 1, NOW, secret="x" * 40)
    assert e.value.code == "bad_signature"


def test_qr_wrong_branch():
    token, _ = qr.issue(2, "kiosk-1", NOW, secret=SECRET)
    with pytest.raises(qr.QrError) as e:
        qr.verify(token, 1, NOW, secret=SECRET)
    assert e.value.code == "wrong_branch"


def test_qr_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("ATTENDANCE_QR_SECRET", raising=False)
    with pytest.raises(qr.QrError) as e:
        qr.issue(1, "kiosk-1", NOW)
    assert e.value.code == "not_configured"


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "x" * 600 + ".y"])
def test_qr_garbage_rejected(token):
    with pytest.raises(qr.QrError):
        qr.verify(token, 1, NOW, secret=SECRET)


class _Db:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, role TEXT)")
        self.conn.executemany("INSERT INTO employees VALUES (?, 'x', 'y')", [(1,), (2,)])

    async def execute(self, q, p=None):
        return self.conn.execute(q, p or []).fetchall()

    async def commit(self):
        self.conn.commit()


def test_qr_redeem_once_per_employee_but_shared_by_team():
    db = _Db()

    async def run():
        await init_attendance_tables(db)
        db.conn.execute("INSERT INTO attendance_branches (id, name) VALUES (1, 'Ofis')")
        for sid, emp in (("s1", 1), ("s2", 1), ("s3", 2)):
            db.conn.execute(
                "INSERT INTO attendance_sessions (id, employee_id, branch_id, kind, work_date, expires_at)"
                " VALUES (?, ?, 1, 'check_in', '2026-10-22', 'x')", [sid, emp])
        _, claims = qr.issue(1, "kiosk-1", NOW, secret=SECRET)
        await qr.record_issued(db, claims)
        await qr.redeem(db, claims, 1, "s1")
        with pytest.raises(qr.QrError) as e:
            await qr.redeem(db, claims, 1, "s2")  # o'sha xodim, o'sha QR — replay
        assert e.value.code == "replayed"
        await qr.redeem(db, claims, 2, "s3")  # boshqa xodim — ruxsat

    asyncio.run(run())


def test_qr_redeem_unknown_nonce_rejected():
    db = _Db()

    async def run():
        await init_attendance_tables(db)
        db.conn.execute("INSERT INTO attendance_branches (id, name) VALUES (1, 'Ofis')")
        _, claims = qr.issue(1, "kiosk-1", NOW, secret=SECRET)  # bazaga yozilmagan
        with pytest.raises(qr.QrError):
            await qr.redeem(db, claims, 1, "s1")

    asyncio.run(run())
