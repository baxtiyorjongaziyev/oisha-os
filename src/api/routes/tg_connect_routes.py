"""Oisha Connect API: menejer oʻz Telegram akkauntini QR orqali ulaydi va boshqaradi.

Har bir endpoint faqat kirgan menejerning OʻZ akkauntiga ishlaydi (Telegram ID = principal).
"""
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.rbac import Permission, Principal, Role, require_permissions
from src.api.routes.attendance_routes import _RateLimiter
from src.services.core.tg_connect import qr_flow, session_ops, store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/connect", tags=["tg-connect"])
_SELF = require_permissions(Permission.TELEGRAM_CONNECT_SELF)
_limiter = _RateLimiter(limit=40, window_s=60)
_qr_limiter = _RateLimiter(limit=6, window_s=300)
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
                await store.init_tables(db)
                _schema_ready = True
    return db


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _employee_id(db, telegram_id: int) -> int | None:
    try:
        rows = await db.execute(
            "SELECT id FROM employees WHERE telegram_id = ? AND is_active = 1", [telegram_id])
    except Exception:  # noqa: BLE001 - employees jadvali hali yoʻq boʻlishi mumkin
        return None
    return int(rows[0]["id"]) if rows else None


async def _me(db, principal: Principal) -> tuple[int, int | None]:
    """Telegram ID va xodim ID. Faqat faol xodim yoki owner ulay oladi."""
    _limiter.check(principal.subject)
    if not principal.subject.isdigit():
        raise HTTPException(status_code=403, detail="telegram_login_required")
    tg = int(principal.subject)
    emp = await _employee_id(db, tg)
    if emp is None and principal.role is not Role.OWNER:
        raise HTTPException(status_code=403, detail="not_an_employee")
    return tg, emp


def _on_done(db, employee_id: int | None, ip: str | None):
    async def done(telegram_id: int, result: dict) -> None:
        await store.save_connected(db, telegram_id, employee_id, result.get("username"), result["session"])
        await store.audit(db, telegram_id, "connected", str(telegram_id), {"device": qr_flow.DEVICE_MODEL}, ip)
        try:
            await store.replace_chats(db, telegram_id, await session_ops.list_dialogs(result["session"]))
        except Exception as exc:  # noqa: BLE001 - roʻyxatni keyin "Yangilash" bilan olsa boʻladi
            logger.warning("tg_connect dialogs fetch failed: %s", type(exc).__name__)
    return done


def _key_ready() -> None:
    if not os.getenv(store.KEY_ENV, "").strip():
        raise HTTPException(status_code=503, detail="connect_not_configured")


class PasswordBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ChatsBody(BaseModel):
    chat_ids: list[int] = Field(default_factory=list, max_length=1000)


@router.get("/status")
async def status(principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    acc = await store.account(db, tg)
    allowed = sum(1 for c in await store.chats(db, tg) if c["allowed"]) if acc else 0
    return {
        "connected": bool(acc and acc["status"] == "connected"),
        "connected_at": acc["connected_at"] if acc else None,
        "username": acc["tg_username"] if acc else None,
        "allowed_chats": allowed,
        "device_name": qr_flow.DEVICE_MODEL,
        "attempt": qr_flow.public_view(qr_flow.get(tg)),
    }


@router.post("/qr/start")
async def qr_start(request: Request, principal: Principal = _SELF):
    _key_ready()
    db = await _ready_db()
    tg, emp = await _me(db, principal)
    _qr_limiter.check(f"qr:{tg}")
    acc = await store.account(db, tg)
    if acc and acc["status"] == "connected":
        raise HTTPException(status_code=409, detail="already_connected")
    att = await qr_flow.start(tg, _on_done(db, emp, _ip(request)))
    return qr_flow.public_view(att)


@router.get("/qr/status")
async def qr_status(principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    return qr_flow.public_view(qr_flow.get(tg))


@router.post("/qr/password")
async def qr_password(body: PasswordBody, request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    tg, emp = await _me(db, principal)
    _qr_limiter.check(f"pw:{tg}")
    state = await qr_flow.submit_password(tg, body.password, _on_done(db, emp, _ip(request)))
    if state in ("no_attempt", "bad_password"):
        raise HTTPException(status_code=400, detail=state)
    return {"state": state}


@router.get("/chats")
async def get_chats(principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    return {"chats": await store.chats(db, tg)}


@router.post("/chats/refresh")
async def refresh_chats(principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    acc = await store.account(db, tg)
    if not acc or acc["status"] != "connected":
        raise HTTPException(status_code=409, detail="not_connected")
    dialogs = await session_ops.list_dialogs(store.decrypt_session(tg, acc["session_enc"]))
    await store.replace_chats(db, tg, dialogs)
    return {"chats": await store.chats(db, tg)}


@router.put("/chats")
async def put_chats(body: ChatsBody, request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    count = await store.set_allowed(db, tg, body.chat_ids)
    await store.audit(db, tg, "chats_updated", str(tg), {"allowed": count}, _ip(request))
    return {"allowed": count}


@router.post("/revoke")
async def revoke(request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    att = qr_flow.get(tg)
    if att is not None:
        await qr_flow.cancel_attempt(att)
        qr_flow.clear(tg)
    if not await session_ops.revoke(db, tg, str(tg), _ip(request)):
        raise HTTPException(status_code=409, detail="not_connected")
    return {"revoked": True}


@router.get("/audit")
async def audit(principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    return {"events": await store.audit_log(db, tg)}


@router.post("/mcp-token")
async def mcp_token(request: Request, principal: Principal = _SELF):
    db = await _ready_db()
    tg, _ = await _me(db, principal)
    try:
        token = await store.issue_mcp_token(db, tg)
    except LookupError:
        raise HTTPException(status_code=409, detail="not_connected")
    await store.audit(db, tg, "mcp_token_issued", str(tg), None, _ip(request))
    return {"token": token, "shown_once": True}


# ---- sahifa ----
# Nginx faqat /api/ ni FastAPI ga yuboradi, shuning uchun sahifa ham /api/ ostida.
APP_PATH = "/api/connect/app"
pages_router = APIRouter(tags=["tg-connect-pages"])
_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "static", "connect")
_HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
            "X-Content-Type-Options": "nosniff", "Permissions-Policy": "camera=(), microphone=(), geolocation=()"}


def _page(name: str):
    from fastapi.responses import FileResponse

    async def serve():
        return FileResponse(os.path.join(_STATIC, name), headers=_HEADERS)
    return serve


for _path, _file in {APP_PATH: "index.html", f"{APP_PATH}/connect.js": "connect.js"}.items():
    pages_router.add_api_route(_path, _page(_file), methods=["GET"], include_in_schema=False)
