"""ERP dashboard routes."""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state

router = APIRouter(prefix="/api/erp", tags=["erp"])
logger = logging.getLogger(__name__)


def _fail(endpoint: str, exc: Exception) -> JSONResponse:
    """Xatoni server tomonda to'liq loglaymiz, mijozga HTTP 500 qaytaramiz.

    Ilgari bu yerda 200 + {"error": ...} qaytardi — buzuq endpoint
    monitoringda sog'lom ko'rinardi va yillab sezilmay qolardi.
    """
    logger.exception("[ERP] %s failed: %s", endpoint, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "endpoint": endpoint},
    )


def _current_period() -> str:
    """Joriy oy, YYYY-MM (ERP moduli shu formatni kutadi)."""
    return date.today().strftime("%Y-%m")


def _is_authorized(request: Request) -> bool:
    import hmac as _hmac
    import os
    secret = (os.environ.get("OISHA_API_SECRET") or "").strip()
    if not secret:
        return False
    auth = request.headers.get("Authorization", "")
    return _hmac.compare_digest(auth, f"Bearer {secret}")


@router.get("/dashboard")
async def erp_dashboard(request: Request, period: str = ""):
    """Oylik ERP kesimi. `period` — YYYY-MM, bo'sh bo'lsa joriy oy."""
    if not _is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        from src.services.core.finance.erp_dashboard import ERPDashboard

        erp = ERPDashboard(db=api_state.db_instance)
        snapshot = await erp.get_snapshot(period or None)
        return asdict(snapshot)
    except Exception as exc:
        return _fail("erp_dashboard", exc)


@router.get("/finance")
async def erp_finance(request: Request, period: str = ""):
    if not _is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        from src.services.core.finance.finance_engine import FinanceEngine

        engine = FinanceEngine(db=api_state.db_instance)
        return await engine.get_cash_flow_summary(period or _current_period())
    except Exception as exc:
        return _fail("erp_finance", exc)


@router.get("/hr")
async def erp_hr(request: Request):
    if not _is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        from src.services.core.hr_engine import HREngine

        engine = HREngine(db=api_state.db_instance)
        return await engine.get_team_summary()
    except Exception as exc:
        return _fail("erp_hr", exc)


@router.get("/projects")
async def erp_projects(request: Request):
    if not _is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        from src.services.core.project_engine import ProjectEngine

        engine = ProjectEngine(db=api_state.db_instance)
        return await engine.get_project_stats()
    except Exception as exc:
        return _fail("erp_projects", exc)


@router.get("/health")
async def erp_health(request: Request):
    if not _is_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    # DB ulanmagan bo'lsa modullar ishlamaydi — buni yashirmaymiz.
    db_connected = api_state.db_instance is not None
    return {
        "status": "ok" if db_connected else "degraded",
        "db_connected": db_connected,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": ["finance", "hr", "projects"],
    }
