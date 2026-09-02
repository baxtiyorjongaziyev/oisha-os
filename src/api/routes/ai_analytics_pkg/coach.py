"""
Sales Coaching, Ideal Scripts and Conversation Quality Analysis API endpoints.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.routes.ai_analytics_pkg.helpers import (
    _ensure_quality_analyzer,
    _fail,
    _unavailable,
)
from src.context import app_ctx

router = APIRouter()


@router.post("/analyze-conversation")
async def analyze_conversation(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not body or not body.get("conversation_text"):
        return JSONResponse(status_code=400, content={"error": "conversation_text_required"})
    from src.services.ai.quality_analyzer import QualityAnalyzer
    analyzer = QualityAnalyzer()
    try:
        res = analyzer.analyze_conversation(
            body.get("conversation_text", ""),
            conversation_id=body.get("conversation_id", "test-1"),
            manager_name=body.get("manager_name", ""),
        )
        import inspect
        analysis = await res if inspect.isawaitable(res) else res
        data = analysis.to_dict() if hasattr(analysis, "to_dict") else (asdict(analysis) if hasattr(analysis, "__dataclass_fields__") else analysis)
        return JSONResponse(status_code=200, content=data)
    except Exception as exc:
        return _fail("/api/ai/analyze-conversation", exc)


@router.get("/metasell-dashboard")
async def get_metasell_dashboard():
    if not getattr(app_ctx, "amocrm", None):
        return _unavailable("/api/ai/metasell-dashboard", "amocrm_uninitialized")
    analyzer = _ensure_quality_analyzer()
    if analyzer is None:
        return _unavailable("/api/ai/metasell-dashboard", "quality_analyzer_uninitialized")
    try:
        dashboard = await analyzer.get_metasell_dashboard()
        return {"success": True, "dashboard": dashboard}
    except Exception as exc:
        return _fail("/api/ai/metasell-dashboard", exc)


@router.get("/coach/daily-report")
async def get_coach_daily_report(manager_name: Optional[str] = None):
    if not getattr(app_ctx, "db", None):
        return _unavailable("/api/ai/coach/daily-report", "db_not_connected")
    try:
        from src.services.ai.sales_coach import SalesCoach
        coach = SalesCoach(db=app_ctx.db)
        report = await coach.generate_daily_coaching_report(manager_name=manager_name)
        return {"success": True, "report": report}
    except Exception as exc:
        return _fail("/api/ai/coach/daily-report", exc)


@router.get("/coach/ideal-script")
async def get_ideal_script(scenario: Optional[str] = None):
    if not getattr(app_ctx, "db", None):
        return _unavailable("/api/ai/coach/ideal-script", "db_not_connected")
    try:
        from src.services.ai.sales_coach import SalesCoach
        coach = SalesCoach(db=app_ctx.db)
        script = await coach.get_ideal_script(scenario=scenario)
        return {"success": True, "script": script}
    except Exception as exc:
        return _fail("/api/ai/coach/ideal-script", exc)


@router.get("/coach/playbook-suggestions")
async def get_playbook_suggestions(topic: Optional[str] = None):
    if not getattr(app_ctx, "db", None):
        return _unavailable("/api/ai/coach/playbook-suggestions", "db_not_connected")
    try:
        from src.services.ai.sales_coach import SalesCoach
        coach = SalesCoach(db=app_ctx.db)
        suggestions = await coach.get_playbook_suggestions(topic=topic)
        return {"success": True, "suggestions": suggestions}
    except Exception as exc:
        return _fail("/api/ai/coach/playbook-suggestions", exc)
