"""
Sales quality routes.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from src.api.rbac import Permission, Principal, require_permissions
from src.services.sales_quality.helpers import (
    _build_empty_sales_quality,
    _build_sales_quality_payload,
    _fetch_call_analysis_rows,
)
from src.services.sales_quality.schemas import SalesQualityAnalysisRequest
from src.api.routes.state import api_state
from src.time_utils import get_local_now

router = APIRouter(tags=["sales-quality"])
logger = logging.getLogger(__name__)


@router.get("/api/sales-quality/overview")
async def get_sales_quality_overview(
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.error("[SALES QUALITY] Real data read failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_build_empty_sales_quality(
                get_local_now().isoformat(),
                f"Real call analytics o'qishda xato: {type(exc).__name__}",
            ),
        )
    return _build_sales_quality_payload(rows, principal=principal)


@router.post(
    "/api/sales-quality/ingest-analysis",
    dependencies=[require_permissions(Permission.CALL_WRITE)],
)
async def ingest_sales_quality_analysis(data: SalesQualityAnalysisRequest):
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(data.secret_key, expected_secret):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
    if not api_state.db_instance:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Database not connected"})

    score = max(0, min(int(data.overall_score), 100))
    now = get_local_now().isoformat()
    analyzed_at = data.analyzed_at or now
    category = data.category or (
        "excellent" if score >= 90 else "good" if score >= 80 else "average" if score >= 60 else "poor"
    )

    conn = await api_state.db_instance.get_connection()
    result = conn.execute(
        """
        INSERT OR REPLACE INTO call_analyses (
            call_id, lead_id, manager_id, manager_name, client_name,
            duration_seconds, overall_score, category, scores, summary,
            strengths, weaknesses, client_mood, client_interest_level,
            objections, outcome, next_steps, recommended_tasks,
            transcript, audio_url, source, analyzed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.call_id, data.lead_id, data.manager_id, data.manager_name,
            data.client_name, max(int(data.duration_seconds or 0), 0), score,
            category, json.dumps(data.scores, ensure_ascii=False), data.summary,
            json.dumps(data.strengths, ensure_ascii=False),
            json.dumps(data.weaknesses, ensure_ascii=False),
            data.client_mood, max(0, min(int(data.client_interest_level or 0), 100)),
            json.dumps(data.objections_raised, ensure_ascii=False), data.outcome,
            json.dumps(data.next_steps, ensure_ascii=False),
            json.dumps(data.recommended_tasks, ensure_ascii=False),
            data.transcript, data.audio_url, data.source, analyzed_at, now,
        ),
    )
    if hasattr(result, "__await__"):
        await result
    commit = getattr(conn, "commit", None)
    if callable(commit):
        committed = commit()
        if hasattr(committed, "__await__"):
            await committed

    return {"status": "ok", "call_id": data.call_id, "source": "real_call_analytics"}


@router.get(
    "/api/sales-quality/conversion-overview",
    dependencies=[
        require_permissions(
            Permission.DASHBOARD_READ,
            Permission.CALL_READ_ALL,
            Permission.FINANCE_READ,
        )
    ],
)
async def sales_quality_conversion_overview(days: int = 30):
    if not api_state.db_instance:
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "reason": "db_not_connected"},
        )
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        window = max(1, min(int(days or 30), 365))
        engine = MetaSellConversionEngine(db=api_state.db_instance)
        return await engine.team_summary(days=window)
    except Exception as exc:
        logger.exception("[SALES QUALITY] conversion-overview failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "endpoint": "conversion_overview"},
        )


@router.get(
    "/dashboard/sales-quality",
    dependencies=[
        require_permissions(
            Permission.DASHBOARD_READ,
            Permission.CALL_READ_ALL,
            Permission.FINANCE_READ,
        )
    ],
)
async def sales_quality_dashboard_html():
    template = (
        Path(__file__).resolve().parent.parent.parent / "api" / "templates"
        / "sales_quality_dashboard.html"
    )
    try:
        return HTMLResponse(content=template.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.error("[SALES QUALITY] Dashboard shabloni o'qilmadi: %s", exc)
        return HTMLResponse(
            content="<h1>Panel vaqtincha ishlamayapti</h1>", status_code=503
        )
