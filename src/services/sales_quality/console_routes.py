"""Metasell Console Parity routes under /api/sales-quality and /dashboard.

Exposes RBAC-protected manager leaderboard (Natija/Sifat + CSV export),
Jon Branding micro-criteria checklist (%), and tool-calling AI Sales Chat
(text + voice STT) backed strictly by real call_analyses data.
"""
from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.api.rbac import Permission, Principal, Role, require_permissions, scope_owned_rows
from src.api.routes.state import api_state
from src.services.core.metasell.checklist import evaluate_manager_checklist
from src.services.core.metasell.leaderboard import (
    build_manager_leaderboard,
    export_leaderboard_csv,
)
from src.services.core.metasell.sales_chat import (
    MetasellSalesChatEngine,
    _SELECT_CHAT_WINDOW_SQL,
    _row_to_mapping,
)
from src.services.sales_quality.schemas import (
    SalesChatAskRequest,
    SalesChatVoiceRequest,
)
from src.services.utils.free_ai_router import get_free_ai_router
from src.time_utils import get_local_now

router = APIRouter(tags=["sales-quality"])
logger = logging.getLogger(__name__)

_MAX_AUDIO_BYTES = 10 * 1024 * 1024


def _clamp_days(days: Optional[int]) -> int:
    return max(1, min(int(days or 30), 365))


async def _load_window_rows(
    days: int, principal: Optional[Principal]
) -> List[Dict[str, Any]]:
    if not api_state.db_instance:
        raise RuntimeError("database_not_connected")
    conn = await api_state.db_instance.get_connection()
    result = conn.execute(_SELECT_CHAT_WINDOW_SQL, (f"-{int(days)} days",))
    if hasattr(result, "__await__"):
        result = await result
    rows = result.fetchall() if hasattr(result, "fetchall") else []
    if hasattr(rows, "__await__"):
        rows = await rows
    mapped = [_row_to_mapping(r) for r in (rows or [])]
    if isinstance(principal, Principal) and principal.role is Role.SELLER:
        return list(scope_owned_rows(principal, mapped, owner_field="manager_id"))
    return mapped


@router.get("/api/sales-quality/leaderboard")
async def get_sales_quality_leaderboard(
    days: int = 30,
    sort_by: str = "natija",
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    window = _clamp_days(days)
    if not api_state.db_instance:
        return JSONResponse(
            status_code=503,
            content={
                "timestamp": get_local_now().isoformat(),
                "source": "real_call_analytics",
                "real_data": False,
                "window_days": window,
                "has_data": False,
                "managers": [],
                "reason": "db_not_connected",
            },
        )
    try:
        rows = await _load_window_rows(window, principal)
    except Exception as exc:
        logger.error("[SALES QUALITY] Leaderboard read failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "timestamp": get_local_now().isoformat(),
                "source": "real_call_analytics",
                "real_data": False,
                "window_days": window,
                "has_data": False,
                "managers": [],
                "reason": type(exc).__name__,
            },
        )
    board = build_manager_leaderboard(rows, sort_by=sort_by)
    return {
        "timestamp": get_local_now().isoformat(),
        "source": "real_call_analytics",
        "real_data": board["has_data"],
        "window_days": window,
        **board,
    }


@router.get("/api/sales-quality/leaderboard.csv")
async def export_sales_quality_leaderboard_csv(
    days: int = 30,
    sort_by: str = "natija",
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    window = _clamp_days(days)
    if not api_state.db_instance:
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "reason": "db_not_connected"},
        )
    try:
        rows = await _load_window_rows(window, principal)
    except Exception as exc:
        logger.error("[SALES QUALITY] CSV export failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "reason": type(exc).__name__},
        )
    board = build_manager_leaderboard(rows, sort_by=sort_by)
    csv_body = "\ufeff" + export_leaderboard_csv(board["managers"])
    mode = board["sort_by"]
    return Response(
        content=csv_body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"menejerlar_reytingi_{mode}_{window}k.csv\""
        },
    )


@router.get("/api/sales-quality/checklist")
async def get_sales_quality_checklist(
    manager_name: Optional[str] = None,
    days: int = 30,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    window = _clamp_days(days)
    if not api_state.db_instance:
        return JSONResponse(
            status_code=503,
            content={
                "timestamp": get_local_now().isoformat(),
                "available": False,
                "reason": "db_not_connected",
                "criteria": [],
                "strengths": [],
                "weaknesses": [],
            },
        )
    try:
        rows = await _load_window_rows(window, principal)
    except Exception as exc:
        logger.error("[SALES QUALITY] Checklist read failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "timestamp": get_local_now().isoformat(),
                "available": False,
                "reason": type(exc).__name__,
                "criteria": [],
                "strengths": [],
                "weaknesses": [],
            },
        )
    profile = evaluate_manager_checklist(rows, manager_name=manager_name)
    return {
        "timestamp": get_local_now().isoformat(),
        "window_days": window,
        **profile,
    }


@router.post("/api/sales-quality/chat")
async def ask_sales_quality_chat(
    req: SalesChatAskRequest,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    question = req.question.strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "question_required"})
    if not api_state.db_instance:
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "reason": "db_not_connected"},
        )
    engine = MetasellSalesChatEngine(
        db=api_state.db_instance,
        ai_router=get_free_ai_router(),
    )
    bounded_history = list(req.history or [])[-8:]
    return await engine.ask(
        question,
        days=req.days,
        history=bounded_history,
        principal=principal if isinstance(principal, Principal) else None,
    )


@router.post("/api/sales-quality/chat/voice")
async def ask_sales_quality_chat_voice(
    req: SalesChatVoiceRequest,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    if not api_state.db_instance:
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "reason": "db_not_connected"},
        )
    try:
        audio_bytes = base64.b64decode(req.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        return JSONResponse(status_code=400, content={"error": "invalid_audio_base64"})
    if not audio_bytes or len(audio_bytes) > _MAX_AUDIO_BYTES:
        return JSONResponse(status_code=400, content={"error": "audio_size_invalid"})

    ai_router = get_free_ai_router()
    stt = await ai_router.transcribe_audio(audio_bytes, req.mime_type or "audio/webm")
    transcript = str(getattr(stt, "text", "") or "").strip() if stt else ""
    if not transcript:
        return JSONResponse(
            status_code=503,
            content={
                "error": "stt_unavailable",
                "reason": "Ovozni matnga aylantirish provayderi ulanmagan yoki ovoz aniqlanmadi.",
            },
        )

    engine = MetasellSalesChatEngine(db=api_state.db_instance, ai_router=ai_router)
    reply = await engine.ask(
        transcript,
        days=req.days,
        history=list(req.history or [])[-8:],
        principal=principal if isinstance(principal, Principal) else None,
    )
    return {"transcript": transcript, **reply}


@router.get(
    "/dashboard/sales-chat",
    dependencies=[
        require_permissions(
            Permission.DASHBOARD_READ,
            Permission.CALL_READ_ALL,
            Permission.FINANCE_READ,
        )
    ],
)
async def sales_chat_dashboard_html() -> HTMLResponse:
    template = (
        Path(__file__).resolve().parent.parent.parent
        / "api"
        / "templates"
        / "sales_quality_dashboard.html"
    )
    try:
        return HTMLResponse(content=template.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.error("[SALES CHAT] Dashboard shabloni oʻqilmadi: %s", exc)
        return HTMLResponse(content="<h1>Panel vaqtincha ishlamayapti</h1>", status_code=503)
