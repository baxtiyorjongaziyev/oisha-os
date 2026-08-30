"""
Helper functions and response utilities for AI Analytics API routes.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi.responses import JSONResponse

from src.api.routes.state import api_state
from src.settings import settings

logger = logging.getLogger(__name__)


def _fail(endpoint: str, exc: Exception) -> JSONResponse:
    logger.exception("[AI] %s failed: %s", endpoint, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "endpoint": endpoint},
    )


def _unavailable(endpoint: str, reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "service_unavailable", "reason": reason, "endpoint": endpoint},
    )


def _deal_hygiene_pipeline_ids() -> list[int]:
    raw = os.getenv("DEAL_HYGIENE_PIPELINES", "")
    if raw:
        try:
            return [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            logger.warning("[AI] DEAL_HYGIENE_PIPELINES parse failed: %s", raw)
    main_pipe = getattr(settings, "AMOCRM_MAIN_PIPELINE_ID", None)
    if main_pipe:
        try:
            return [int(main_pipe)]
        except (TypeError, ValueError):
            pass
    return []


def _ensure_quality_analyzer() -> Optional[Any]:
    if api_state.quality_analyzer is None:
        try:
            from src.services.ai.quality_analyzer import QualityAnalyzer

            api_state.quality_analyzer = QualityAnalyzer()
        except Exception as exc:
            logger.warning("[AI] QualityAnalyzer init failed: %s", exc)
            return None
    return api_state.quality_analyzer
