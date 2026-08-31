"""
Composite router for AI Analytics.
Delegates to modular subpackage in src.api.routes.ai_analytics_pkg.
"""
from fastapi import APIRouter

from src.api.rbac import Permission, require_permissions
from src.api.routes.ai_analytics_pkg.coach import router as coach_router
from src.api.routes.ai_analytics_pkg.conversion import router as conversion_router
from src.api.routes.ai_analytics_pkg.calls import router as calls_router
from src.api.routes.ai_analytics_pkg.helpers import (
    _deal_hygiene_pipeline_ids,
    _ensure_quality_analyzer,
    _fail,
    _unavailable,
)

router = APIRouter(
    prefix="/api/ai",
    tags=["ai-analytics"],
)

router.include_router(coach_router)
router.include_router(conversion_router)
router.include_router(calls_router)

__all__ = [
    "router",
    "_fail",
    "_unavailable",
    "_deal_hygiene_pipeline_ids",
    "_ensure_quality_analyzer",
]
