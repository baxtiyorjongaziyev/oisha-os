"""Oisha Connect MCP endpoint (ChatGPT / Claude uchun).

Kalit ikki usulda beriladi:
- ``Authorization: Bearer oc_...`` (Claude Code, Claude Desktop, API);
- URL ichida ``/api/connect/mcp/oc_...`` (sarlavha qoʻyib boʻlmaydigan konnektorlar uchun).
Kalit faqat hash koʻrinishida saqlanadi; sahifada yangisini yaratish eskisini bekor qiladi.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from src.api.routes.attendance_routes import _RateLimiter
from src.api.routes.tg_connect_routes import _ready_db
from src.services.core.tg_connect import mcp_server, store

router = APIRouter(prefix="/api/connect/mcp", tags=["tg-connect-mcp"])
_limiter = _RateLimiter(limit=60, window_s=60)
_UNAUTH = JSONResponse({"error": "invalid_token"}, status_code=401,
                       headers={"WWW-Authenticate": 'Bearer realm="oisha-connect"'})


def _bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else None


async def _serve(request: Request, token: Optional[str]) -> Response:
    if not token:
        return _UNAUTH
    db = await _ready_db()
    acc = await store.account_by_mcp_token(db, token)
    if acc is None:
        return _UNAUTH
    tg = int(acc["telegram_id"])
    _limiter.check(f"mcp:{tg}")
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(mcp_server._err(None, -32700, "Parse error"), status_code=400)
    if isinstance(body, list):
        out = [r for r in [await mcp_server.handle(db, tg, m) for m in body[:20]] if r is not None]
        return JSONResponse(out) if out else Response(status_code=202)
    res = await mcp_server.handle(db, tg, body)
    return JSONResponse(res) if res is not None else Response(status_code=202)


@router.post("")
async def mcp_header(request: Request):
    return await _serve(request, _bearer(request))


@router.post("/{token}")
async def mcp_path(token: str, request: Request):
    return await _serve(request, token)


@router.get("")
@router.get("/{token}")
async def mcp_get():
    # Server-initiated SSE oqimi yoʻq (holatsiz server).
    return Response(status_code=405, headers={"Allow": "POST"})
