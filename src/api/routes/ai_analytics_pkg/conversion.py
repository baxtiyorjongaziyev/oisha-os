"""
Conversion, seller cards, and deal hygiene API routes.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.rbac import Permission, require_permissions
from src.api.routes.ai_analytics_pkg.helpers import (
    _deal_hygiene_pipeline_ids,
    _fail,
    _unavailable,
)
from src.api.routes.state import api_state

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_DAYS = 365


def _window(days: int) -> int:
    return max(1, min(int(days or 30), _MAX_DAYS))


def _engine():
    """DB ulanganida conversion engine, aks holda None."""
    from src.services.core.metasell_conversion import MetaSellConversionEngine

    if api_state.db_instance is None:
        return None
    return MetaSellConversionEngine(db=api_state.db_instance)


def _db_unavailable(endpoint: str) -> JSONResponse:
    return _unavailable(f"/api/ai/conversion/{endpoint}", "db_not_connected")


def _sync_days(body: Dict[str, Any]) -> int:
    raw = body.get("days")
    if raw is not None:
        return max(1, min(int(raw), 366))
    start, end = body.get("start_date"), body.get("end_date")
    if start and end:
        span = (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days
        return max(1, min(span + 1, 366))
    return 90


def _volume_payload(volumes: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value.to_dict() if hasattr(value, "to_dict") else value
        for key, value in volumes.items()
    }


@router.get("/conversion/overview", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def get_conversion_overview(days: int = 30):
    engine = _engine()
    if engine is None:
        return _db_unavailable("overview")
    try:
        overview = await engine.team_summary(days=_window(days))
        return {"success": True, "overview": overview}
    except Exception as exc:
        return _fail("/api/ai/conversion/overview", exc)


@router.get("/conversion/trend")
async def get_conversion_trend(days: int = 30):
    engine = _engine()
    if engine is None:
        return _db_unavailable("trend")
    try:
        trend = await engine.conversion_trend(days=_window(days))
        return {"success": True, "trend": trend.to_dict()}
    except Exception as exc:
        return _fail("/api/ai/conversion/trend", exc)


@router.post("/conversion/sync-revenue", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def sync_revenue(request: Request):
    from src.context import app_ctx

    if api_state.db_instance is None:
        return _db_unavailable("sync-revenue")
    if not getattr(app_ctx, "amocrm", None):
        return _unavailable("/api/ai/conversion/sync-revenue", "amocrm_uninitialized")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        from src.services.core.metasell_revenue import MetaSellRevenueSync

        result = await MetaSellRevenueSync(
            db=api_state.db_instance, amocrm=app_ctx.amocrm
        ).sync(days=_sync_days(body))
        return {"success": True, "result": result.to_dict()}
    except Exception as exc:
        return _fail("/api/ai/conversion/sync-revenue", exc)


@router.get("/conversion/volume")
async def get_conversion_volume(days: int = 30):
    engine = _engine()
    if engine is None:
        return _db_unavailable("volume")
    try:
        volume = await engine.fetch_volumes(days=_window(days))
        return {"success": True, "volume": _volume_payload(volume)}
    except Exception as exc:
        return _fail("/api/ai/conversion/volume", exc)


@router.get("/conversion/seller-card", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def get_seller_card(seller_name: str, days: int = 30):
    engine = _engine()
    if engine is None:
        return _db_unavailable("seller-card")
    try:
        window = _window(days)
        diagnoses = await engine.diagnose_all(days=window)
        target = next(
            (item for item in diagnoses if item.manager_name == seller_name), None
        )
        if target is None:
            return JSONResponse(
                status_code=404,
                content={"error": "seller_not_found", "seller_name": seller_name},
            )
        volumes = await engine.fetch_volumes(days=window)
        card = engine.build_seller_card(target, volumes.get(target.manager_name))
        return {
            "success": True,
            "seller_name": target.manager_name,
            "card": card,
            "diagnosis": target.to_dict(),
        }
    except Exception as exc:
        return _fail("/api/ai/conversion/seller-card", exc)


@router.get("/deal-hygiene")
async def get_deal_hygiene(dry_run: bool = True):
    from src.context import app_ctx
    if not getattr(app_ctx, "amocrm", None):
        return _unavailable("/api/ai/deal-hygiene", "amocrm_uninitialized")
    try:
        from src.services.core.crm.crm_cleaner import CRMCleaner

        cleaner = CRMCleaner(amocrm=app_ctx.amocrm)
        result = await cleaner.audit_hygiene(
            pipeline_ids=_deal_hygiene_pipeline_ids(),
            dry_run=dry_run,
        )
        return {"success": True, "audit": result}
    except Exception as exc:
        return _fail("/api/ai/deal-hygiene", exc)


@router.post("/deal-hygiene/apply")
async def apply_deal_hygiene(request: Request):
    try:
        body = await request.json()
        from src.context import app_ctx
        from src.services.core.crm.crm_cleaner import CRMCleaner

        cleaner = CRMCleaner(amocrm=getattr(app_ctx, "amocrm", None))
        result = await cleaner.apply_hygiene_fixes(
            lead_ids=body.get("lead_ids", []),
            action=body.get("action", "archive"),
        )
        return {"success": True, "result": result}
    except Exception as exc:
        return _fail("/api/ai/deal-hygiene/apply", exc)
