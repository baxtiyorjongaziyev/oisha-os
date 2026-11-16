"""Davomatda yuz tasdig'i: roʻyxatdan oʻtish, jonlilik (bosh burish), urinishlar chegarasi."""
import sqlite3
from types import SimpleNamespace

import pytest

from src.services.core.attendance import face_engine, face_verify
from src.services.core.attendance.face_engine import FaceReading

ME = (1.0, 0.0, 0.0)
ME_CLOSE = (0.9, 0.4359, 0.0)   # kosinus ≈ 0.9
STRANGER = (0.0, 1.0, 0.0)      # kosinus 0
T0 = 1_000_000


class SqliteDb:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, q, p=None):
        return self.conn.execute(q, p or []).fetchall()

    async def commit(self):
        self.conn.commit()


class FakeEngine:
    def __init__(self):
        self.next = []

    def analyze(self, image):
        return self.next


def reading(vec=ME, yaw=0.0):
    return FaceReading(vec, yaw)


@pytest.fixture
def db():
    return SqliteDb()


@pytest.fixture
def engine():
    return FakeEngine()


async def _enrolled(db, engine):
    assert await face_verify.start_enroll(db, 1, now=T0)
    engine.next = [reading()]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0) == "enrolled"


async def test_enroll_once_only(db, engine):
    await _enrolled(db, engine)
    assert await face_verify.is_enrolled(db, 1)
    assert await face_verify.start_enroll(db, 1, now=T0) is False


async def test_enroll_requires_frontal_single_face(db, engine):
    await face_verify.start_enroll(db, 1, now=T0)
    engine.next = [reading(yaw=40)]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0) == "not_frontal"
    engine.next = [reading(), reading()]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0) == "many_faces"
    engine.next = []
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0) == "no_face"
    assert not await face_verify.is_enrolled(db, 1)


async def test_verify_happy_path(db, engine):
    await _enrolled(db, engine)
    assert await face_verify.start_verify(db, 1, now=T0)
    engine.next = [reading(ME_CLOSE, yaw=3)]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + 5) == "need_turn"
    engine.next = [reading(ME_CLOSE, yaw=-32)]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + 15) == "verified"
    assert await face_verify.recently_verified(db, 1, now=T0 + 20)
    assert not await face_verify.recently_verified(db, 1, now=T0 + 20 + face_verify.VERIFIED_WINDOW_S + 1)


async def test_stranger_rejected(db, engine):
    await _enrolled(db, engine)
    await face_verify.start_verify(db, 1, now=T0)
    engine.next = [reading(STRANGER)]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + 1) == "no_match"
    assert not await face_verify.recently_verified(db, 1, now=T0 + 2)


async def test_replayed_frontal_photo_fails_turn_step(db, engine):
    """Telefon ekranidagi bitta toʻgʻri rasm ikkinchi (burilgan) bosqichdan oʻtmaydi."""
    await _enrolled(db, engine)
    await face_verify.start_verify(db, 1, now=T0)
    engine.next = [reading(ME_CLOSE, yaw=2)]
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + 1) == "need_turn"
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + 2) == "not_turned"
    assert not await face_verify.recently_verified(db, 1, now=T0 + 3)


async def test_too_many_attempts_clears_challenge(db, engine):
    await _enrolled(db, engine)
    await face_verify.start_verify(db, 1, now=T0)
    engine.next = [reading(STRANGER)]
    codes = [await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + i) for i in range(face_verify.MAX_ATTEMPTS)]
    assert codes[-1] == "too_many"
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=T0 + 9) == "no_challenge"


async def test_challenge_expires(db, engine):
    await _enrolled(db, engine)
    await face_verify.start_verify(db, 1, now=T0)
    engine.next = [reading(ME_CLOSE)]
    late = T0 + face_verify.CHALLENGE_TTL_S + 1
    assert await face_verify.submit_photo(db, engine, 1, b"x", now=late) == "no_challenge"


async def test_verify_needs_enrollment(db):
    assert await face_verify.start_verify(db, 1, now=T0) is False


async def test_reset_allows_reenroll(db, engine):
    await _enrolled(db, engine)
    await face_verify.reset(db, 1)
    assert not await face_verify.is_enrolled(db, 1)
    assert await face_verify.start_enroll(db, 1, now=T0)


def test_required_flag(monkeypatch):
    monkeypatch.delenv("ATTENDANCE_FACE_REQUIRED", raising=False)
    assert face_verify.required() is False
    monkeypatch.setenv("ATTENDANCE_FACE_REQUIRED", "1")
    assert face_verify.required() is True


def test_cosine_basics():
    assert face_engine.cosine(ME, ME) == pytest.approx(1.0)
    assert face_engine.cosine(ME, STRANGER) == pytest.approx(0.0)
    assert face_engine.cosine((1.0,), (1.0, 0.0)) == -1.0


async def test_photo_without_challenge_is_left_for_other_handlers(monkeypatch):
    from aiogram.dispatcher.event.bases import UNHANDLED

    from src.services.core.attendance import repo
    from src.services.core.dispatcher import handlers_attendance as h

    async def fake_employee(db, tg):
        return {"id": 1, "name": "X"}

    async def no_challenge(db, employee_id, now=None):
        return None

    monkeypatch.setattr(repo, "employee_by_telegram", fake_employee)
    monkeypatch.setattr(face_verify, "get_challenge", no_challenge)
    msg = SimpleNamespace(chat=SimpleNamespace(type="private"), from_user=SimpleNamespace(id=7))
    assert await h.handle_photo(msg) is UNHANDLED
