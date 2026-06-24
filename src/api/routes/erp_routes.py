"""ERP dashboard routes."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request

from src.api.routes.state import api_state
from src.settings import settings

router = APIRouter(prefix="/api/erp", tags=["erp"])
logger = logging.getLogger(__name__)


def _is_authorized(request: Request) -> bool:
    import hmac as _hmac
    import os
    secret = (os.environ.get("OISHA_API_SECRET") or "").strip()
    if not secret:
        return False
    auth = request.headers.get("Authorization", "")
    return _hmac.compare_digest(auth, f"Bearer {secret}")


@router.get("/dashboard")
async def erp_dashboard(request: Request):
    if not _is_authorized(request):
        return {"error": "Unauthorized"}
    try:
        from src.services.core.erp_dashboard import ERPDashboard
        erp = ERPDashboard(db=api_state.db_instance)
        return await erp.get_dashboard_summary()
    except Exception as exc:
        logger.error("[ERP] Dashboard error: %s", exc)
        return {"error": str(exc)}


@router.get("/finance")
async def erp_finance(request: Request):
    if not _is_authorized(request):
        return {"error": "Unauthorized"}
    try:
        from src.services.core.finance_engine import FinanceEngine
        engine = FinanceEngine(db=api_state.db_instance)
        return await engine.get_finance_summary()
    except Exception as exc:
        logger.error("[ERP] Finance error: %s", exc)
        return {"error": str(exc)}


@router.get("/hr")
async def erp_hr(request: Request):
    if not _is_authorized(request):
        return {"error": "Unauthorized"}
    try:
        from src.services.core.hr_engine import HREngine
        engine = HREngine(db=api_state.db_instance)
        return await engine.get_hr_summary()
    except Exception as exc:
        logger.error("[ERP] HR error: %s", exc)
        return {"error": str(exc)}


@router.get("/projects")
async def erp_projects(request: Request):
    if not _is_authorized(request):
        return {"error": "Unauthorized"}
    try:
        from src.services.core.project_engine import ProjectEngine
        engine = ProjectEngine(db=api_state.db_instance)
        return await engine.get_projects_summary()
    except Exception as exc:
        logger.error("[ERP] Projects error: %s", exc)
        return {"error": str(exc)}


@router.get("/health")
async def erp_health(request: Request):
    if not _is_authorized(request):
        return {"error": "Unauthorized"}
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": ["finance", "hr", "projects"],
    }
