"""AI analytics routes — Metasell-style quality analytics."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state
from src.settings import settings
from src.time_utils import get_local_now

router = APIRouter(prefix="/api/ai", tags=["ai-analytics"])
logger = logging.getLogger(__name__)


def _secret_check(request: Request) -> bool:
    expected = os.environ.get("OISHA_API_SECRET")
    if not expected:
        return True
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


@router.post("/analyze-conversation")
async def analyze_conversation(request: Request):
    if not _secret_check(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        data = await request.json()
        conversation = data.get("conversation", [])
        lead_id = data.get("lead_id")

        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        result = await analyzer.analyze_conversation(conversation, lead_id=lead_id)
        return result
    except Exception as exc:
        logger.error("[AI] analyze_conversation error: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/dashboard")
async def ai_dashboard():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_dashboard_summary()
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/manager-ratings")
async def ai_manager_ratings():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_manager_ratings()
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/lost-clients-analysis")
async def ai_lost_clients():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_lost_clients_analysis()
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/create-tasks-from-analysis")
async def create_tasks_from_analysis(request: Request):
    if not _secret_check(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        data = await request.json()
        analysis_id = data.get("analysis_id")
        from src.services.ai import AITaskManager
        manager = AITaskManager(db=api_state.db_instance, amocrm=api_state.amocrm_instance)
        return await manager.create_tasks_from_analysis(analysis_id)
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/metasell-dashboard")
async def metasell_dashboard():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_metasell_dashboard()
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/call-details/{call_id}")
async def get_call_details(call_id: str):
    try:
        from src.services.ai import CallAnalytics
        analytics = CallAnalytics(db=api_state.db_instance)
        return await analytics.get_call_details(call_id)
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/skills-radar")
async def ai_skills_radar():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_skills_radar()
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/trend-analysis")
async def ai_trend_analysis(days: int = 30):
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_trend_analysis(days=days)
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/manager-comparison")
async def ai_manager_comparison():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_manager_comparison()
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/lead-classifier")
async def ai_lead_classifier():
    try:
        from src.services.core.lead_classifier import LeadClassifier
        classifier = LeadClassifier(db=api_state.db_instance)
        return await classifier.get_classification_summary()
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/lead-classifier/tag")
async def ai_lead_classifier_tag(request: Request):
    if not _secret_check(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        data = await request.json()
        lead_id = data.get("lead_id")
        from src.services.core.lead_classifier import LeadClassifier
        classifier = LeadClassifier(db=api_state.db_instance)
        return await classifier.classify_lead(lead_id)
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/deal-hygiene")
async def ai_deal_hygiene():
    try:
        from src.services.core.deal_hygiene import AmoCRMDealHygieneAgent
        agent = AmoCRMDealHygieneAgent(db=api_state.db_instance, amocrm=api_state.amocrm_instance)
        return await agent.get_hygiene_report()
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/deal-hygiene/apply")
async def ai_deal_hygiene_apply(request: Request):
    if not _secret_check(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        from src.services.core.deal_hygiene import AmoCRMDealHygieneAgent
        agent = AmoCRMDealHygieneAgent(db=api_state.db_instance, amocrm=api_state.amocrm_instance)
        return await agent.apply_hygiene_fixes()
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/process-call")
async def ai_process_call(request: Request):
    if not _secret_check(request):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    try:
        data = await request.json()
        call_id = data.get("call_id")
        audio_url = data.get("audio_url")
        from src.services.ai.conversation_engine import get_conversation_engine
        engine = get_conversation_engine(db=api_state.db_instance)
        return await engine.process_call(call_id=call_id, audio_url=audio_url)
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/daily-report")
async def ai_daily_report():
    try:
        from src.services.ai import QualityAnalyzer
        analyzer = QualityAnalyzer(db=api_state.db_instance)
        return await analyzer.get_daily_report()
    except Exception as exc:
        return {"error": str(exc)}
