"""Davomatda yuzni tasdiqlash: roʻyxatdan oʻtish (enroll) va "keldim" oldidan jonlilik tekshiruvi.

Oqim:
- ``/yuz`` — xodim bir marta toʻgʻri qarab selfi yuboradi, faqat vektor saqlanadi (rasm emas).
- ``/keldim`` — bot ikki rasm soʻraydi: toʻgʻri qarab, soʻng boshni yon tomonga burib. Ikkalasida ham
  yuz roʻyxatdagi yuzga mos boʻlishi, ikkinchisida bosh burilgan boʻlishi shart. Bu telefon ekranidagi
  yoki qogʻozdagi bitta rasm bilan aldashni toʻxtatadi.
- Tasdiqdan keyin ``VERIFIED_WINDOW_S`` ichida joylashuv tugmasi "keldi" belgisini qoʻyadi.

``ATTENDANCE_FACE_REQUIRED=1`` boʻlmasa, tekshiruv majburiy emas (bosqichma-bosqich joriy qilish).
Bosh burilish yoʻnalishi (chap/oʻng) tekshirilmaydi: old kamera tasviri aks etgan boʻlishi mumkin va
qurilmada sinalmagan. Faqat burilish kattaligi (|yaw|) tekshiriladi.
"""
from __future__ import annotations

import asyncio
import json
import os
import time

from src.services.core.attendance import repo
from src.services.core.attendance.face_engine import FaceEngine, cosine

MATCH_THRESHOLD = 0.40        # toʻgʻri qarashdagi oʻxshashlik (ArcFace kosinus)
TURNED_MATCH_THRESHOLD = 0.30  # burilgan yuz uchun yumshoqroq
MAX_FRONTAL_YAW = 15.0
MIN_TURN_YAW = 20.0
CHALLENGE_TTL_S = 120
ENROLL_TTL_S = 300
VERIFIED_WINDOW_S = 600
MAX_ATTEMPTS = 5

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS attendance_faces (
        employee_id INTEGER PRIMARY KEY,
        embedding TEXT NOT NULL,
        created_at INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS attendance_face_challenge (
        employee_id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL,
        stage INTEGER NOT NULL DEFAULT 0,
        attempts INTEGER NOT NULL DEFAULT 0,
        expires_at INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS attendance_face_ok (
        employee_id INTEGER PRIMARY KEY,
        verified_at INTEGER NOT NULL)""",
]


def required() -> bool:
    return os.getenv("ATTENDANCE_FACE_REQUIRED", "0").strip().lower() in ("1", "true", "yes")


async def init_tables(db) -> None:
    for ddl in _SCHEMA:
        await db.execute(ddl)
    await db.commit()


async def is_enrolled(db, employee_id: int) -> bool:
    await init_tables(db)
    return await repo.one(db, "SELECT 1 FROM attendance_faces WHERE employee_id = ?", [employee_id]) is not None


async def recently_verified(db, employee_id: int, now: int | None = None) -> bool:
    await init_tables(db)
    row = await repo.one(db, "SELECT verified_at FROM attendance_face_ok WHERE employee_id = ?", [employee_id])
    return row is not None and int(time.time() if now is None else now) - int(row["verified_at"]) <= VERIFIED_WINDOW_S


async def get_challenge(db, employee_id: int, now: int | None = None):
    """Faol (muddati oʻtmagan) soʻrov yoki None."""
    await init_tables(db)
    now = int(time.time() if now is None else now)
    row = await repo.one(db, "SELECT kind, stage, attempts, expires_at FROM attendance_face_challenge"
                         " WHERE employee_id = ?", [employee_id])
    if row is None:
        return None
    if int(row["expires_at"]) < now:
        await _clear_challenge(db, employee_id)
        return None
    return row


async def _clear_challenge(db, employee_id: int) -> None:
    await db.execute("DELETE FROM attendance_face_challenge WHERE employee_id = ?", [employee_id])
    await db.commit()


async def _set_challenge(db, employee_id: int, kind: str, ttl: int, now: int) -> None:
    await db.execute(
        "INSERT INTO attendance_face_challenge (employee_id, kind, stage, attempts, expires_at)"
        " VALUES (?, ?, 0, 0, ?) ON CONFLICT (employee_id) DO UPDATE SET kind = excluded.kind, stage = 0,"
        " attempts = 0, expires_at = excluded.expires_at", [employee_id, kind, now + ttl])
    await db.commit()


async def start_enroll(db, employee_id: int, now: int | None = None) -> bool:
    """False — allaqachon roʻyxatdan oʻtgan (qayta oʻtkazish faqat rahbar orqali)."""
    if await is_enrolled(db, employee_id):
        return False
    await _set_challenge(db, employee_id, "enroll", ENROLL_TTL_S, int(time.time() if now is None else now))
    return True


async def start_verify(db, employee_id: int, now: int | None = None) -> bool:
    """False — yuz roʻyxatdan oʻtmagan."""
    if not await is_enrolled(db, employee_id):
        return False
    await _set_challenge(db, employee_id, "verify", CHALLENGE_TTL_S, int(time.time() if now is None else now))
    return True


async def reset(db, employee_id: int) -> None:
    await init_tables(db)
    for table in ("attendance_faces", "attendance_face_challenge", "attendance_face_ok"):
        await db.execute(f"DELETE FROM {table} WHERE employee_id = ?", [employee_id])  # nosec B608
    await db.commit()


async def _fail(db, employee_id: int, code: str) -> str:
    await db.execute("UPDATE attendance_face_challenge SET attempts = attempts + 1 WHERE employee_id = ?",
                     [employee_id])
    row = await repo.one(db, "SELECT attempts FROM attendance_face_challenge WHERE employee_id = ?", [employee_id])
    await db.commit()
    if row is not None and int(row["attempts"]) >= MAX_ATTEMPTS:
        await _clear_challenge(db, employee_id)
        return "too_many"
    return code


async def submit_photo(db, engine: FaceEngine, employee_id: int, image: bytes, now: int | None = None) -> str:
    """Rasmni baholaydi. Natija kodi: no_challenge, enrolled, need_turn, verified yoki xato kodi
    (no_face, many_faces, not_frontal, no_match, not_turned, too_many)."""
    now = int(time.time() if now is None else now)
    challenge = await get_challenge(db, employee_id, now)
    if challenge is None:
        return "no_challenge"
    faces = await asyncio.to_thread(engine.analyze, image)
    if not faces:
        return await _fail(db, employee_id, "no_face")
    if len(faces) > 1:
        return await _fail(db, employee_id, "many_faces")
    face = faces[0]
    kind, stage = str(challenge["kind"]), int(challenge["stage"])

    if kind == "enroll":
        if abs(face.yaw) > MAX_FRONTAL_YAW:
            return await _fail(db, employee_id, "not_frontal")
        await db.execute(
            "INSERT INTO attendance_faces (employee_id, embedding, created_at) VALUES (?, ?, ?)"
            " ON CONFLICT (employee_id) DO NOTHING", [employee_id, json.dumps(list(face.embedding)), now])
        await db.commit()
        await _clear_challenge(db, employee_id)
        return "enrolled"

    stored = await repo.one(db, "SELECT embedding FROM attendance_faces WHERE employee_id = ?", [employee_id])
    if stored is None:
        await _clear_challenge(db, employee_id)
        return "no_challenge"
    similarity = cosine(json.loads(stored["embedding"]), face.embedding)

    if stage == 0:
        if abs(face.yaw) > MAX_FRONTAL_YAW:
            return await _fail(db, employee_id, "not_frontal")
        if similarity < MATCH_THRESHOLD:
            return await _fail(db, employee_id, "no_match")
        await db.execute("UPDATE attendance_face_challenge SET stage = 1 WHERE employee_id = ?", [employee_id])
        await db.commit()
        return "need_turn"

    if abs(face.yaw) < MIN_TURN_YAW:
        return await _fail(db, employee_id, "not_turned")
    if similarity < TURNED_MATCH_THRESHOLD:
        return await _fail(db, employee_id, "no_match")
    await db.execute(
        "INSERT INTO attendance_face_ok (employee_id, verified_at) VALUES (?, ?)"
        " ON CONFLICT (employee_id) DO UPDATE SET verified_at = excluded.verified_at", [employee_id, now])
    await db.commit()
    await _clear_challenge(db, employee_id)
    return "verified"
