"""Avtomatik "keldi/ketdi": Telegram jonli lokatsiya (asosiy) va ofis Wi-Fi avtomatikasi.

Owner qarori (2026-10-26): koordinatalar saqlanmaydi. Har lokatsiya kelganda faqat
"ofis hududida / tashqarida" hisoblanadi, koordinata tashlab yuboriladi. Bazada
`attendance_auto_state` da faqat holat (ichkarida/tashqarida, vaqt) turadi.

Qoidalar:
- Faqat ish oynasida (07:00–21:00 Toshkent) belgi qo'yiladi.
- Hududga kirdi va bugun hali kelmagan → `check_in`.
- Bugun kelgan, hali ketmagan, soat 17:00 dan keyin va 15 daqiqa aniq tashqarida → `check_out`.
  17:00 gacha chiqib ketish tanaffus hisoblanadi (kuniga bitta keldi/ketdi bor);
  erta ketishni xodim o'zi "Ketdim" bilan belgilaydi.
- "Aniq tashqarida" = masofa − aniqlik > radius (chegarada tebranish ketdi qilmaydi).

Wi-Fi: telefondagi avtomatika (iPhone Qisqa buyruqlar / Android MacroDroid) ofis
Wi-Fi'ga ulanganda va uzilganda shaxsiy kalit bilan so'rov yuboradi. Kelish faqat
ofis tashqi IP'sidan qabul qilinadi; ketish (Wi-Fi uzilgan, mobil internet) kalit bilan.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime
from typing import Optional

from src.services.core.attendance import audit, repo
from src.services.core.attendance import geofence as gf
from src.services.core.attendance.service import Actor, AttendanceError, AttendanceService
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

WORK_START_HOUR, WORK_END_HOUR = 7, 21
EARLIEST_AUTO_LEAVE_HOUR = 17
LEAVE_AFTER_SECONDS = 15 * 60
DEFAULT_ACCURACY_M = 30.0
TOKEN_PREFIX = "oaw_"

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS attendance_auto_state (
        employee_id INTEGER PRIMARY KEY,
        inside INTEGER NOT NULL,
        outside_since INTEGER,
        last_seen INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS attendance_auto_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_by TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        last_used_at INTEGER,
        revoked_at INTEGER)""",
]

CHECK_IN, CHECK_OUT = "check_in", "check_out"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def init_tables(db) -> None:
    for ddl in _SCHEMA:
        await db.execute(ddl)
    await db.commit()


def in_work_window(now_local: Optional[datetime] = None) -> bool:
    hour = (now_local or get_local_now()).hour
    return WORK_START_HOUR <= hour < WORK_END_HOUR


def leave_allowed(now_local: Optional[datetime] = None) -> bool:
    return (now_local or get_local_now()).hour >= EARLIEST_AUTO_LEAVE_HOUR


def classify(fence: gf.Geofence, lat: float, lon: float, accuracy_m: float) -> Optional[bool]:
    """True: aniq ichkarida; False: aniq tashqarida; None: noaniq (hech narsa qilinmaydi)."""
    distance = gf.haversine_m(fence.latitude, fence.longitude, lat, lon)
    acc = min(max(accuracy_m, 0.0), 1000.0)
    if acc <= fence.max_accuracy_m and distance + acc <= fence.radius_m:
        return True
    if distance - acc > fence.radius_m:
        return False
    return None


async def _actor_for_telegram(db, telegram_id: int) -> Optional[Actor]:
    emp = await repo.employee_by_telegram(db, str(telegram_id))
    if emp is None:
        return None
    return Actor(employee_id=int(emp["id"]), name=str(emp["name"]), subject=str(telegram_id))


async def _today_flags(db, svc: AttendanceService, employee_id: int) -> tuple[str, bool, bool]:
    from src.services.core.attendance import rules

    day = rules.resolve_work_date(svc.shift, svc.clock()).isoformat()
    came = await repo.confirmed_exists(db, employee_id, day, CHECK_IN)
    left = await repo.confirmed_exists(db, employee_id, day, CHECK_OUT)
    return day, came, left


async def _punch(svc: AttendanceService, actor: Actor, kind: str, day: str, method: str) -> Optional[str]:
    try:
        await svc.auto_punch(actor, kind, f"auto-{method}-{actor.employee_id}-{day}-{kind}", method)
        return kind
    except AttendanceError as e:
        if e.code not in ("already_recorded", "check_in_required"):
            logger.warning("[AUTO-ATT] %s %s rad etildi: %s", actor.name, kind, e.code)
        return None


async def on_location(db, telegram_id: int, latitude: float, longitude: float,
                      accuracy_m: Optional[float], *, service: Optional[AttendanceService] = None,
                      now_local: Optional[datetime] = None) -> Optional[str]:
    """Telegram lokatsiyasi. Qo'yilgan belgi ("check_in"/"check_out") yoki None."""
    await init_tables(db)
    actor = await _actor_for_telegram(db, telegram_id)
    if actor is None:
        return None
    row = await repo.active_geofence(db)
    if row is None:
        return None
    fence = gf.Geofence(float(row["latitude"]), float(row["longitude"]),
                        int(row["radius_m"]), int(row["max_accuracy_m"]))
    inside = classify(fence, latitude, longitude, accuracy_m or DEFAULT_ACCURACY_M)
    del latitude, longitude  # koordinata shu yerdan keyin ishlatilmaydi va saqlanmaydi
    if inside is None:
        return None
    now = int(time.time())
    state = await repo.one(db, "SELECT inside, outside_since FROM attendance_auto_state WHERE employee_id=?",
                           [actor.employee_id])
    outside_since = None
    if not inside:
        outside_since = int(state["outside_since"]) if state is not None and state["outside_since"] else now
    await db.execute(
        """INSERT INTO attendance_auto_state(employee_id, inside, outside_since, last_seen)
        VALUES (?,?,?,?) ON CONFLICT(employee_id) DO UPDATE SET inside=excluded.inside,
        outside_since=excluded.outside_since, last_seen=excluded.last_seen""",
        [actor.employee_id, int(inside), outside_since, now],
    )
    await db.commit()
    if not in_work_window(now_local):
        return None
    svc = service or AttendanceService(db)
    day, came, left = await _today_flags(db, svc, actor.employee_id)
    if inside and not came:
        return await _punch(svc, actor, CHECK_IN, day, "telegram_live_location")
    if (not inside and came and not left and leave_allowed(now_local)
            and now - outside_since >= LEAVE_AFTER_SECONDS):
        return await _punch(svc, actor, CHECK_OUT, day, "telegram_live_location")
    return None


# ---- Wi-Fi avtomatika: shaxsiy kalit ----
async def create_token(db, *, actor: str, employee_id: int, ip: str | None = None) -> str:
    await init_tables(db)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    await db.execute(
        """UPDATE attendance_auto_tokens SET revoked_at=? WHERE employee_id=? AND revoked_at IS NULL""",
        [int(time.time()), employee_id],
    )
    await db.execute(
        """INSERT INTO attendance_auto_tokens(employee_id, token_hash, created_by, created_at)
        VALUES (?,?,?,?)""",
        [employee_id, _hash(token), actor, int(time.time())],
    )
    await audit.log(db, actor=actor, action="auto_token_created", entity="employee",
                    entity_id=employee_id, details={}, ip=ip)
    await db.commit()
    return token


async def employee_for_token(db, token: str) -> Optional[Actor]:
    if not token.startswith(TOKEN_PREFIX) or len(token) > 128:
        return None
    await init_tables(db)
    rows = await db.execute(
        """UPDATE attendance_auto_tokens SET last_used_at=? WHERE token_hash=? AND revoked_at IS NULL
        RETURNING employee_id""",
        [int(time.time()), _hash(token)],
    )
    await db.commit()
    if not rows:
        return None
    emp = await repo.one(db, "SELECT id, name FROM employees WHERE id=? AND is_active=1",
                         [int(rows[0]["employee_id"])])
    if emp is None:
        return None
    return Actor(employee_id=int(emp["id"]), name=str(emp["name"]), subject=f"wifi:{emp['id']}")


async def on_wifi(db, actor: Actor, event: str, on_office_ip: Optional[bool], *,
                  service: Optional[AttendanceService] = None,
                  now_local: Optional[datetime] = None) -> Optional[str]:
    """event: "join" (ofis Wi-Fi'ga ulandi) yoki "leave" (uzildi)."""
    if event not in ("join", "leave") or not in_work_window(now_local):
        return None
    svc = service or AttendanceService(db)
    day, came, left = await _today_flags(db, svc, actor.employee_id)
    if event == "join":
        if on_office_ip is not True:  # Wi-Fi sozlanmagan yoki ofis IP'si emas — kelish qabul qilinmaydi
            return None
        return None if came else await _punch(svc, actor, CHECK_IN, day, "office_wifi_auto")
    if came and not left and leave_allowed(now_local):
        return await _punch(svc, actor, CHECK_OUT, day, "office_wifi_auto")
    return None

