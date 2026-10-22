"""Smart Attendance sozlash API: xodimni bog'lash so'rovlari va ofis monitori kalitlari."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.rbac import Permission, Principal, require_permissions
from src.api.routes.attendance_routes import LocationBody, _actor, _db, _ip, _limiter, _raise, _ready_db, _service
from datetime import timezone

from src.services.core.attendance import bootstrap, kiosk, linking, network
from src.services.core.attendance.geofence import LocationFix
from src.services.core.attendance.notifier import default_notifier
from src.services.core.attendance.service import AttendanceError

router = APIRouter(prefix="/api/attendance", tags=["attendance-setup"])
_SELF = require_permissions(Permission.ATTENDANCE_SELF)
_MANAGE = require_permissions(Permission.ATTENDANCE_MANAGE)


class LinkBody(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class ApproveBody(BaseModel):
    employee_id: int | None = None  # bo'sh — yangi xodim yaratiladi


class KioskBody(BaseModel):
    label: str = Field(default="Ofis monitori", min_length=2, max_length=60)


def _tg(principal: Principal) -> int:
    if not principal.subject.isdigit():
        raise HTTPException(status_code=403, detail="telegram_login_required")
    return int(principal.subject)


# ---- xodim: o'zini bog'lash ----
@router.get("/link-request")
async def link_status(principal: Principal = _SELF):
    db = await _ready_db()
    return {"state": await linking.status(db, _tg(principal))}


@router.post("/link-request")
async def link_request(body: LinkBody, request: Request, principal: Principal = _SELF):
    _limiter.check(f"link:{principal.subject}")
    db = await _ready_db()
    try:
        res = await linking.request(db, telegram_id=_tg(principal), full_name=body.full_name, ip=_ip(request))
    except AttendanceError as e:
        _raise(e)
    await default_notifier().notify_review(
        f"👤 Davomatga ulanish so'rovi: {res['name']}\nHR panel → Jamoa va grafik → So'rovlar")
    return res


# ---- admin ----
@router.get("/admin/link-requests")
async def admin_link_requests(principal: Principal = _MANAGE):
    db = await _ready_db()
    return {"requests": await linking.pending(db), "unlinked_employees": await linking.unlinked_employees(db)}


@router.post("/admin/link-requests/{request_id}/approve")
async def admin_link_approve(request_id: int, body: ApproveBody, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    try:
        res = await linking.approve(db, actor=principal.subject, request_id=request_id,
                                    employee_id=body.employee_id, ip=_ip(request))
    except AttendanceError as e:
        _raise(e)
    await bootstrap.run(db)  # yangi bog'langan xodimga owner bergan grafik qo'llanadi
    return res


@router.post("/admin/link-requests/{request_id}/reject")
async def admin_link_reject(request_id: int, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    try:
        await linking.reject(db, actor=principal.subject, request_id=request_id, ip=_ip(request))
    except AttendanceError as e:
        _raise(e)
    return {"state": "rejected"}


@router.get("/admin/kiosk-tokens")
async def admin_kiosk_tokens(principal: Principal = _MANAGE):
    db = await _ready_db()
    return {"tokens": await kiosk.list_tokens(db)}


@router.post("/admin/kiosk-tokens")
async def admin_kiosk_create(body: KioskBody, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    token = await kiosk.create(db, actor=principal.subject, label=body.label, ip=_ip(request))
    # Kalit faqat shu javobda bir marta ko'rsatiladi; bazada xeshi saqlanadi.
    return {"token": token, "url": f"/api/attendance/app/kiosk#k={token}"}


@router.delete("/admin/kiosk-tokens/{token_id}")
async def admin_kiosk_revoke(token_id: int, request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    if not await kiosk.revoke(db, actor=principal.subject, token_id=token_id, ip=_ip(request)):
        raise HTTPException(status_code=404, detail="token_not_found")
    return {"revoked": True}


# ---- soddalashtirilgan: bir bosishda GPS + ofis Wi-Fi ----
class PunchBody(LocationBody):
    kind: str = Field(pattern="^(check_in|check_out)$")


@router.post("/punch")
async def punch(body: PunchBody, request: Request, principal: Principal = _SELF,
                idempotency_key: str = Header(default="", alias="Idempotency-Key")):
    db = await _ready_db()
    actor = await _actor(db, principal, request)
    wifi = await network.is_office(db, network.client_ip(request)) if await network.configured(db) else None
    captured = body.captured_at if body.captured_at.tzinfo else body.captured_at.replace(tzinfo=timezone.utc)
    fix = LocationFix(body.latitude, body.longitude, body.accuracy_m, captured, body.is_mocked)
    try:
        return await _service(db).punch(actor, body.kind, idempotency_key, fix, wifi)
    except AttendanceError as e:
        _raise(e)


@router.get("/admin/office-wifi")
async def admin_wifi_list(request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    ip = network.client_ip(request)
    return {"networks": await network.list_all(db), "your_ip": ip,
            "you_are_on_office_wifi": await network.is_office(db, ip)}


@router.post("/admin/office-wifi")
async def admin_wifi_add(request: Request, principal: Principal = _MANAGE):
    db = await _ready_db()
    try:
        return await network.add(db, actor=principal.subject, ip=network.client_ip(request), label="Ofis Wi-Fi")
    except AttendanceError as e:
        _raise(e)


@router.delete("/admin/office-wifi/{network_id}")
async def admin_wifi_remove(network_id: int, principal: Principal = _MANAGE):
    db = await _ready_db()
    if not await network.remove(db, actor=principal.subject, network_id=network_id):
        raise HTTPException(status_code=404, detail="network_not_found")
    return {"removed": True}


__all__ = ["router", "_db"]
