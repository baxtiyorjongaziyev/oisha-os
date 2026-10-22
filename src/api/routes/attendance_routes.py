"""Smart Attendance API (/api/attendance/*).

Auth: mavjud Oisha sessiyasi (Telegram login → ``oisha_token``). Xodim Telegram ID si
faol ``employees.telegram_id`` ga bog'langan bo'lishi shart. Admin amallari RBAC bilan.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from src.api.rbac import Permission, Principal, require_permissions
from src.services.core.attendance import admin as att_admin
from src.services.core.attendance import audit, bootstrap, export, kiosk, qr_tokens, reports, repo, rules, summary
from src.services.core.attendance.secrets_util import qr_secret
from src.services.core.attendance.geofence import LocationFix
from src.services.core.attendance.notifier import default_notifier
from src.services.core.attendance.schema import init_attendance_tables
from src.services.core.attendance.service import Actor, AttendanceError, AttendanceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/attendance", tags=["attendance"])

_SELF = require_permissions(Permission.ATTENDANCE_SELF)
_READ_ALL = require_permissions(Permission.ATTENDANCE_READ_ALL)
_MANAGE = require_permissions(Permission.ATTENDANCE_MANAGE)


# ---- infra ----
class _RateLimiter:
    """Jarayon ichidagi sliding window. Bitta Contabo jarayoni uchun yetarli."""

    def __init__(self, limit: int, window_s: float):
        self.limit, self.window_s = limit, window_s
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(status_code=429, detail="rate_limited")
        q.append(now)


_limiter = _RateLimiter(limit=30, window_s=60)
_schema_lock = asyncio.Lock()
_schema_ready = False


def _db():
    from src.database_pool import db_pool

    return db_pool


async def _ready_db():
    global _schema_ready
    db = _db()
    if not _schema_ready:
        async with _schema_lock:
            if not _schema_ready:
                await init_attendance_tables(db)
                try:
                    await bootstrap.run(db)
                except Exception:
                    logger.exception("[ATTENDANCE] bootstrap failed")
                _schema_ready = True
    return db


def _service(db) -> AttendanceService:
    return AttendanceService(db, notifier=default_notifier(), qr_secret=qr_secret())


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _raise(exc: AttendanceError):
    raise HTTPException(status_code=exc.status, detail=exc.code)


async def _actor(db, principal: Principal, request: Request) -> Actor:
    _limiter.check(principal.subject)
    if not principal.subject.isdigit():
        raise HTTPException(status_code=403, detail="not_an_employee")
    emp = await repo.employee_by_telegram(db, principal.subject)
    if emp is None:
        raise HTTPException(status_code=403, detail="not_an_employee")
    return Actor(employee_id=int(emp["id"]), name=str(emp["name"]), subject=principal.subject, ip=_ip(request))


# ---- schemas ----
class StartBody(BaseModel):
    kind: str = Field(pattern="^(check_in|check_out)$")


class LocationBody(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=100_000)
    captured_at: datetime
    is_mocked: bool | None = None


class QrBody(BaseModel):
    token: str = Field(min_length=10, max_length=512)


class OfficeBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(ge=10, le=5000)
    max_accuracy_m: int = Field(default=50, ge=5, le=500)


class ScheduleBody(BaseModel):
    weekdays: list[int] = Field(min_length=1, max_length=7, description="ISO: 1=Du ... 7=Ya")
    start: str = Field(default="10:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="19:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    optional_weekdays: list[int] = Field(default_factory=list, max_length=7)
    valid_from: date | None = None


class CorrectionBody(BaseModel):
    employee_id: int
    work_date: date
    new_status: str
    reason: str = Field(min_length=5, max_length=1000)
    event_id: int | None = None


# ---- xodim ----
@router.post("/sessions")
async def start_session(body: StartBody, request: Request, principal: Principal = _SELF,
                        idempotency_key: str = Header(default="", alias="Idempotency-Key")):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    try:
        return await _service(db).start(actor, body.kind, idempotency_key)
    except AttendanceError as e:
        _raise(e)


@router.post("/sessions/{sid}/location")
async def submit_location(sid: str, body: LocationBody, request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    captured = body.captured_at if body.captured_at.tzinfo else body.captured_at.replace(tzinfo=timezone.utc)
    fix = LocationFix(body.latitude, body.longitude, body.accuracy_m, captured, body.is_mocked)
    try:
        return await _service(db).submit_location(sid, actor, fix)
    except AttendanceError as e:
        _raise(e)


@router.post("/sessions/{sid}/qr")
async def submit_qr(sid: str, body: QrBody, request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    try:
        return await _service(db).submit_qr(sid, actor, body.token)
    except AttendanceError as e:
        _raise(e)


@router.post("/sessions/{sid}/face")
async def submit_face(sid: str, request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    try:
        return await _service(db).submit_face(sid, actor)
    except AttendanceError as e:
        _raise(e)


@router.post("/sessions/{sid}/confirm")
async def confirm(sid: str, request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    try:
        return await _service(db).confirm(sid, actor)
    except AttendanceError as e:
        _raise(e)


@router.get("/today")
async def today(request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    d = datetime.now(timezone(timedelta(hours=5))).date()
    return {"date": d.isoformat(), "events": await reports.events(db, d, d, actor.employee_id)}


@router.get("/history")
async def history(request: Request, principal: Principal = _SELF, days: int = Query(30, ge=1, le=366)):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    end = datetime.now(timezone(timedelta(hours=5))).date()
    return {"events": await reports.events(db, end - timedelta(days=days - 1), end, actor.employee_id)}


# ---- kiosk (ofis monitori) ----
async def _kiosk_allowed(db, request: Request) -> bool:
    """Monitor kaliti (HR panelida yaratiladi) yoki kiosk/manage huquqli sessiya."""
    from src.api.rbac import has_permission
    from src.api.security import authorize_connection

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and await kiosk.verify(db, auth[7:].strip()):
        return True
    principal = authorize_connection(request)
    return principal is not None and (has_permission(principal, Permission.ATTENDANCE_KIOSK)
                                      or has_permission(principal, Permission.ATTENDANCE_MANAGE))


# Yo'l security._PUBLIC_PATHS da: autentifikatsiya shu yerda (_kiosk_allowed), fail-closed.
@router.get("/kiosk/qr")
async def kiosk_qr(request: Request, kiosk_id: str = Query("main", pattern="^[A-Za-z0-9_-]{1,32}$")):
    db = await _ready_db()
    _limiter.check(f"kiosk:{_ip(request)}")
    if not await _kiosk_allowed(db, request):
        raise HTTPException(status_code=401, detail="kiosk_unauthorized")
    fence = await repo.active_geofence(db)
    if fence is None:
        raise HTTPException(status_code=503, detail="geofence_not_configured")
    try:
        token, claims = qr_tokens.issue(int(fence["branch_id"]), kiosk_id, datetime.now(timezone.utc),
                                        secret=qr_secret())
    except qr_tokens.QrError as e:
        raise HTTPException(status_code=503, detail=f"qr_{e.code}") from None
    await qr_tokens.record_issued(db, claims)
    return {"token": token, "expires_at": claims.expires_at.isoformat(), "refresh_in_s": 25}


# ---- admin ----
@router.get("/admin/dashboard")
async def admin_dashboard(principal: Principal = _READ_ALL, day: date | None = None):
    db = await _ready_db()
    svc = _service(db)
    d = day or datetime.now(timezone(timedelta(hours=5))).date()
    return await reports.dashboard(db, d, svc.calendar)


@router.get("/admin/reports")
async def admin_reports(start: date, end: date, request: Request, principal: Principal = _READ_ALL,
                        employee_id: int | None = None,
                        status: str | None = Query(None, pattern="^[A-Z_]{3,20}$"),
                        view: str = Query("events", pattern="^(events|summary)$"),
                        format: str = Query("json", pattern="^(json|xlsx|pdf)$")):
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail="invalid_range")
    db = await _ready_db()
    if view == "summary":
        today = datetime.now(timezone(timedelta(hours=5))).date()
        rows = await summary.period_summary(db, start, end, today=today, employee_id=employee_id)
        columns, title = export.SUMMARY_COLUMNS, "Davomat xulosasi"
    else:
        rows = await reports.events(db, start, end, employee_id, status)
        columns, title = export.EVENT_COLUMNS, "Davomat yozuvlari"
    await audit.log(db, actor=principal.subject, action="report_viewed", entity="attendance_report",
                    details={"view": view, "format": format, "start": start, "end": end}, ip=_ip(request))
    await db.commit()
    if format == "json":
        return {"view": view, "start": start.isoformat(), "end": end.isoformat(), "rows": rows}
    headers, table = export.table(rows, columns)
    stem = f"davomat-{view}-{start.isoformat()}-{end.isoformat()}"
    if format == "xlsx":
        body, media = export.to_xlsx(headers, table), \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body, media = export.to_pdf(title, f"{start.isoformat()} — {end.isoformat()}", headers, table), \
            "application/pdf"
    return Response(content=body, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{stem}.{format}"', "Cache-Control": "no-store"})


@router.get("/admin/employees")
async def admin_employees(principal: Principal = _READ_ALL):
    db = await _ready_db()
    today = datetime.now(timezone(timedelta(hours=5))).date().isoformat()
    out = []
    for emp in await repo.employees_active(db):
        shift = rules.shift_from_row(await repo.employee_shift(db, int(emp["id"]), today))
        out.append({"id": int(emp["id"]), "name": emp["name"], "weekdays": sorted(shift.weekdays),
                    "optional_weekdays": sorted(shift.optional_weekdays),
                    "start": shift.start.strftime("%H:%M"), "end": shift.end.strftime("%H:%M")})
    return {"employees": out}


@router.post("/admin/corrections")
async def admin_correction(body: CorrectionBody, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    try:
        return await att_admin.apply_correction(
            db, actor=principal.subject, employee_id=body.employee_id, work_date=body.work_date.isoformat(),
            new_status=body.new_status, reason=body.reason, event_id=body.event_id, ip=_ip(request))
    except AttendanceError as e:
        _raise(e)


@router.put("/admin/office")
async def admin_office(body: OfficeBody, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    return await att_admin.configure_office(
        db, actor=principal.subject, name=body.name, latitude=body.latitude, longitude=body.longitude,
        radius_m=body.radius_m, max_accuracy_m=body.max_accuracy_m, ip=_ip(request))


@router.put("/admin/schedules/{employee_id}")
async def admin_schedule(employee_id: int, body: ScheduleBody, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    start_day = body.valid_from or datetime.now(timezone(timedelta(hours=5))).date()
    try:
        return await att_admin.set_schedule(
            db, actor=principal.subject, employee_id=employee_id, weekdays=body.weekdays,
            start=body.start, end=body.end, valid_from=start_day.isoformat(),
            optional_weekdays=body.optional_weekdays, ip=_ip(request))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_schedule") from None
    except AttendanceError as e:
        _raise(e)


# ---- sahifalar ----
# Prod Nginx faqat /api/* ni backend'ga yuboradi (deploy/nginx-oisha.conf), shuning uchun ekranlar
# /api/attendance/app ostida. Qobiqlar ochiq (security._PUBLIC_PATHS), ma'lumot esa RBAC bilan.
APP_PREFIX = "/api/attendance/app"
pages_router = APIRouter(tags=["attendance-pages"])
_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "static", "attendance")
PAGES = {
    APP_PREFIX: "employee.html", f"{APP_PREFIX}/kiosk": "kiosk.html", f"{APP_PREFIX}/admin": "admin.html",
    f"{APP_PREFIX}/common.js": "common.js", f"{APP_PREFIX}/employee.js": "employee.js",
    f"{APP_PREFIX}/admin.js": "admin.js",
}
_HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
            "X-Content-Type-Options": "nosniff",
            "Permissions-Policy": "geolocation=(self), camera=(self), microphone=()"}


def _page(name: str):
    from fastapi.responses import FileResponse

    media = "text/javascript" if name.endswith(".js") else "text/html"

    async def serve():
        return FileResponse(os.path.join(_STATIC, name), media_type=media, headers=_HEADERS)
    return serve


for _path, _file in PAGES.items():
    pages_router.add_api_route(_path, _page(_file), methods=["GET"], include_in_schema=False)
