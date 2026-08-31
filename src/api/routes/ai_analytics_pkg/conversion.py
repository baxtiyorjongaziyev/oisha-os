"""
Conversion, seller cards, and deal hygiene API routes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

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


@router.get("/conversion/overview", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def get_conversion_overview(days: int = 30):
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        engine = MetaSellConversionEngine()
        overview = await engine.get_overview(days=days)
        return {"success": True, "overview": overview}
    except Exception as exc:
        return _fail("/api/ai/conversion/overview", exc)


@router.get("/conversion/trend")
async def get_conversion_trend(days: int = 30):
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        engine = MetaSellConversionEngine()
        trend = await engine.get_trend(days=days)
        return {"success": True, "trend": trend}
    except Exception as exc:
        return _fail("/api/ai/conversion/trend", exc)


@router.post("/conversion/sync-revenue", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def sync_revenue(request: Request):
    try:
        body = await request.json()
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        engine = MetaSellConversionEngine()
        result = await engine.sync_revenue(
            start_date=body.get("start_date"),
            end_date=body.get("end_date"),
        )
        return {"success": True, "result": result}
    except Exception as exc:
        return _fail("/api/ai/conversion/sync-revenue", exc)


@router.get("/conversion/volume")
async def get_conversion_volume(days: int = 30):
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        engine = MetaSellConversionEngine()
        volume = await engine.get_volume(days=days)
        return {"success": True, "volume": volume}
    except Exception as exc:
        return _fail("/api/ai/conversion/volume", exc)


@router.get("/conversion/seller-card", dependencies=[require_permissions(Permission.FINANCE_READ)])
async def get_seller_card(seller_id: int, days: int = 30):
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        engine = MetaSellConversionEngine()
        card = await engine.get_seller_card(seller_id=seller_id, days=days)
        return {"success": True, "card": card}
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
