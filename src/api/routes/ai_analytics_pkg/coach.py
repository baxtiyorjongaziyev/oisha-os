"""
Coach, conversation analysis and call processing routes.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.rbac import Permission, require_permissions
from src.api.routes.ai_analytics_pkg.helpers import (
    _ensure_quality_analyzer,
    _fail,
    _unavailable,
)
from src.api.routes.state import api_state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze-conversation")
async def analyze_conversation(request: Request):
    analyzer = _ensure_quality_analyzer()
    if analyzer is None:
        return _unavailable("/api/ai/analyze-conversation", "quality_analyzer_uninitialized")
    try:
        body = await request.json()
        transcript = body.get("transcript", "")
        if not transcript.strip():
            return JSONResponse(status_code=400, content={"error": "transcript_empty"})
        analysis = await analyzer.analyze_conversation(
            transcript=transcript,
            manager_name=body.get("manager_name", "Noma'lum"),
            client_name=body.get("client_name", "Noma'lum"),
            context=body.get("context", {}),
        )
        return {"success": True, "analysis": asdict(analysis) if hasattr(analysis, "__dataclass_fields__") else analysis}
    except Exception as exc:
        return _fail("/api/ai/analyze-conversation", exc)


@router.get("/metasell-dashboard")
async def get_metasell_dashboard():
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
    try:
        from src.services.ai.sales_coach import SalesCoach

        coach = SalesCoach()
        report = await coach.generate_daily_coaching_report(manager_name=manager_name)
        return {"success": True, "report": report}
    except Exception as exc:
        return _fail("/api/ai/coach/daily-report", exc)


@router.get("/coach/ideal-script")
async def get_ideal_script(scenario: str = "general"):
    try:
        from src.services.ai.sales_coach import SalesCoach

        coach = SalesCoach()
        script = await coach.get_ideal_script(scenario=scenario)
        return {"success": True, "script": script}
    except Exception as exc:
        return _fail("/api/ai/coach/ideal-script", exc)


@router.get("/coach/playbook-suggestions")
async def get_playbook_suggestions(topic: str = "general"):
    try:
        from src.services.ai.sales_coach import SalesCoach

        coach = SalesCoach()
        suggestions = await coach.get_playbook_suggestions(topic=topic)
        return {"success": True, "suggestions": suggestions}
    except Exception as exc:
        return _fail("/api/ai/coach/playbook-suggestions", exc)


@router.post("/process-call")
async def process_call(request: Request):
    try:
        body = await request.json()
        lead_id = body.get("lead_id")
        audio_url = body.get("audio_url")
        if not lead_id or not audio_url:
            return JSONResponse(
                status_code=400,
                content={"error": "lead_id and audio_url required"},
            )
        from src.context import app_ctx

        runner = getattr(app_ctx, "call_analytics_runner", None)
        if runner is None:
            return _unavailable("/api/ai/process-call", "call_analytics_runner_uninitialized")
        result = await runner.process_call_recording(
            lead_id=int(lead_id),
            audio_url=str(audio_url),
            duration_sec=int(body.get("duration_sec", 0)),
            phone=body.get("phone", ""),
        )
        return {"success": True, "result": result}
    except Exception as exc:
        return _fail("/api/ai/process-call", exc)


@router.post("/lead-classifier/tag")
async def tag_lead(request: Request):
    try:
        body = await request.json()
        lead_id = body.get("lead_id")
        text = body.get("text", "")
        if not lead_id or not text:
            return JSONResponse(
                status_code=400,
                content={"error": "lead_id and text required"},
            )
        from src.services.ai.lead_classifier import LeadClassifier

        classifier = LeadClassifier()
        result = await classifier.classify_and_tag(lead_id=int(lead_id), text=str(text))
        return {"success": True, "result": result}
    except Exception as exc:
        return _fail("/api/ai/lead-classifier/tag", exc)
