"""AI analytics routes — Metasell-style quality analytics.

Bu router ilgari 16 ta endpoint e'lon qilardi, lekin ularning hech biri
ishlamasdi: handlerlar mavjud bo'lmagan konstruktor imzolari va metod
nomlarini chaqirar, xatolik esa `except: return {"error": ...}` bilan
HTTP 200 ostida yashirinardi.

Endi shu yerda faqat haqiqiy xizmatga ulangan endpointlar qoldi.

Olib tashlanganlar va sababi:
- `/dashboard`, `/manager-ratings`, `/lost-clients-analysis`, `/skills-radar`,
  `/trend-analysis`, `/manager-comparison`, `/daily-report`, `/call-details/{id}`
  va `/lead-classifier` — `QualityAnalyzer`/`CallAnalytics`/`LeadClassifier`
  natijalarni faqat xotirada saqlaydi
  (`add_analysis` ro'yxatga qo'shadi, restart'da yo'qoladi), shuning uchun bu
  yerda ko'rsatiladigan doimiy ma'lumot yo'q edi. Haqiqiy, DB'ga tayangan
  savdo sifati paneli allaqachon mavjud: `GET /api/sales-quality/overview`
  (`call_analyses` jadvalidan o'qiydi).
- `/create-tasks-from-analysis` — `AITaskManager.create_tasks_from_analysis`
  `ConversationAnalysis` obyektini kutadi, endpoint esa `analysis_id` yuborardi;
  id bo'yicha tahlilni topadigan saqlash qatlami yo'q.
"""
from __future__ import annotations

import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from src.api.rbac import Permission, require_permissions
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state
from src.settings import settings

router = APIRouter(
    prefix="/api/ai",
    tags=["ai-analytics"],
    dependencies=[require_permissions(Permission.CALL_READ_ALL)],
)
logger = logging.getLogger(__name__)


def _fail(endpoint: str, exc: Exception) -> JSONResponse:
    """Xatoni server tomonda to'liq loglaymiz, mijozga HTTP 500 qaytaramiz.

    Ilgari bu yerda 200 + {"error": ...} qaytardi — buzuq endpoint
    monitoringda sog'lom ko'rinardi va yillab sezilmay qolardi.
    """
    logger.exception("[AI] %s failed: %s", endpoint, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "endpoint": endpoint},
    )


def _unavailable(endpoint: str, reason: str) -> JSONResponse:
    """Kerakli bog'liqlik ulanmagan — 503, chunki bu vaqtinchalik holat."""
    logger.warning("[AI] %s unavailable: %s", endpoint, reason)
    return JSONResponse(
        status_code=503,
        content={"error": "service_unavailable", "reason": reason},
    )


def _secret_check(request: Request) -> bool:
    expected = os.environ.get("OISHA_API_SECRET")
    if not expected:
        return True
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


def _unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"error": "Unauthorized"})


@router.post("/analyze-conversation")
async def analyze_conversation(request: Request):
    """Suhbat matnini sifat rubrikasi bo'yicha baholaydi."""
    if not _secret_check(request):
        return _unauthorized()
    try:
        data = await request.json()
        text = str(data.get("conversation_text") or "").strip()
        if not text:
            return JSONResponse(
                status_code=400,
                content={"error": "conversation_text is required"},
            )

        from src.services.ai import QualityAnalyzer

        analyzer = QualityAnalyzer()
        # Haqiqiy LLM baholash; Gemini yo'q bo'lsa evristikaga tushadi va
        # javobdagi `scoring_method` buni ochiq ko'rsatadi.
        analysis = await analyzer.analyze_conversation_ai(
            conversation_text=text,
            conversation_id=str(data.get("conversation_id") or ""),
            lead_id=data.get("lead_id"),
            manager_id=data.get("manager_id"),
            manager_name=str(data.get("manager_name") or ""),
            duration_seconds=int(data.get("duration_seconds") or 0),
        )
        return analysis.to_dict()
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("analyze_conversation", exc)


@router.get("/metasell-dashboard")
async def metasell_dashboard():
    """Savdo sifati paneli — `call_analyses` jadvalidagi haqiqiy tahlillar.

    `/api/sales-quality/overview` bilan bir xil manba va format; bu yo'l
    tashqi skilllar (openclaw) uchun saqlanib qolgan.
    """
    from src.api.routes.sales_quality import (
        _build_sales_quality_payload,
        _fetch_call_analysis_rows,
    )

    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _unavailable(
            "metasell_dashboard", f"db_read_failed: {type(exc).__name__}"
        )

    try:
        return _build_sales_quality_payload(rows)
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("metasell_dashboard", exc)


@router.get("/coach/daily-report")
async def coach_daily_report(request: Request, day: str = ""):
    """Kunlik savdo sifati: eng yaxshi sotuvchi + o'sish nuqtalari.

    `day` — YYYY-MM-DD, bo'sh bo'lsa bugun. Bu hisobot har kuni 20:00 da
    Telegram'ga ham yuboriladi.
    """
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("coach_daily_report", "db_not_connected")
    try:
        from src.services.core.sales_quality_coach import SalesQualityCoach
        from src.time_utils import get_local_now

        day_iso = day or get_local_now().strftime("%Y-%m-%d")
        coach = SalesQualityCoach(db=api_state.db_instance)
        report = await coach.generate_daily_report(day_iso)
        return {
            "day": day_iso,
            "report": report,
            "has_data": report is not None,
        }
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("coach_daily_report", exc)


@router.get("/coach/ideal-script")
async def coach_ideal_script(request: Request):
    """Eng yaxshi qo'ng'iroqlardan sintez qilingan ideal skript (taklif)."""
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("coach_ideal_script", "db_not_connected")
    try:
        from src.services.core.sales_quality_coach import SalesQualityCoach

        coach = SalesQualityCoach(db=api_state.db_instance)
        script = await coach.generate_ideal_script()
        if script is None:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "not_enough_samples",
                    "hint": "Kamida 3 ta yuqori baholi (75+) transkripsiya kerak",
                },
            )
        # Bu — taklif, rasmiy playbook emas.
        return {"script": script, "status": "draft_suggestion"}
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("coach_ideal_script", exc)


@router.get("/coach/playbook-suggestions")
async def coach_playbook_suggestions(request: Request):
    """Oxirgi hafta zaifliklari asosida playbook takliflari.

    Playbook avtomatik o'zgarmaydi — bu faqat tavsiya.
    """
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("coach_playbook_suggestions", "db_not_connected")
    try:
        from src.services.core.sales_quality_coach import SalesQualityCoach

        coach = SalesQualityCoach(db=api_state.db_instance)
        suggestions = await coach.suggest_playbook_improvements()
        if suggestions is None:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "not_enough_data",
                    "hint": "Oxirgi 7 kunda kamida 5 ta qayd etilgan zaiflik kerak",
                },
            )
        return {"suggestions": suggestions, "status": "advisory_only"}
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("coach_playbook_suggestions", exc)


@router.get("/conversion/overview")
async def conversion_overview(request: Request, days: int = 30):
    """Jamoa konversiyasi + har bir sotuvchining o'sish nuqtasi.

    Ball emas, KONVERSIYA bo'yicha saflaydi: qaysi bosqich aynan shu
    sotuvchida bitimni yo'qotayotganini konvertirlangan va konvertirlanmagan
    qo'ng'iroqlar ballarini solishtirib topadi.
    """
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("conversion_overview", "db_not_connected")
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        window = max(1, min(int(days or 30), 365))
        engine = MetaSellConversionEngine(db=api_state.db_instance)
        return await engine.team_summary(days=window)
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("conversion_overview", exc)


@router.get("/conversion/trend")
async def conversion_trend(request: Request, days: int = 30):
    """Konversiya trendi — joriy davr oldingi davrga nisbatan.

    Farq FOIZ PUNKTIDA (pp) beriladi: 22% dan 50% ga o'sish = +28 pp.
    Ma'lumot yetarli bo'lmasa `reliable: false` va sababi qaytadi.
    """
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("conversion_trend", "db_not_connected")
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        window = max(1, min(int(days or 30), 365))
        engine = MetaSellConversionEngine(db=api_state.db_instance)
        trend = await engine.conversion_trend(days=window)
        return trend.to_dict()
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("conversion_trend", exc)


@router.post("/conversion/sync-revenue")
async def conversion_sync_revenue(request: Request, days: int = 90):
    """AmoCRM'dan bitim narxi va yakunini `call_analyses` ga ko'chiradi.

    Odatda haftalik job avtomatik bajaradi; bu yo'l qo'lda ishga tushirish
    uchun (masalan birinchi to'ldirishda).
    """
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("conversion_sync_revenue", "db_not_connected")
    try:
        # AmoCRM klientini mavjud yagona joydan olamiz — bu yerda qayta
        # qurish ikkinchi token oqimini paydo qiladi.
        from src.api.routes.amocrm_integration import _get_amocrm_instance
        from src.services.core.metasell_revenue import MetaSellRevenueSync

        amocrm = _get_amocrm_instance()
        if amocrm is None:
            return _unavailable("conversion_sync_revenue", "amocrm_not_connected")

        window = max(1, min(int(days or 90), 365))
        result = await MetaSellRevenueSync(db=api_state.db_instance, amocrm=amocrm).sync(
            days=window
        )
        return result.to_dict()
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("conversion_sync_revenue", exc)


@router.get("/conversion/volume")
async def conversion_volume(request: Request, days: int = 30):
    """Qo'ng'iroq hajmi: jami / samarali / o'tkazib yuborilgan / o'rtacha.

    Javobsiz qo'ng'iroqlar `call_events` jadvalida — ular hech qanday ball
    olmaydi, shuning uchun sifat statistikasida ko'rinmaydi.
    """
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("conversion_volume", "db_not_connected")
    try:
        from src.services.core.call_events import CallEventLog

        window = max(1, min(int(days or 30), 365))
        return await CallEventLog(db=api_state.db_instance).volume_summary(days=window)
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("conversion_volume", exc)


@router.get("/conversion/seller-card")
async def conversion_seller_card(request: Request, manager: str = "", days: int = 30):
    """Bitta sotuvchi uchun haftalik o'sish kartochkasi (Telegram matni)."""
    if not _secret_check(request):
        return _unauthorized()
    if api_state.db_instance is None:
        return _unavailable("conversion_seller_card", "db_not_connected")
    if not manager.strip():
        return JSONResponse(
            status_code=400, content={"error": "manager is required"}
        )
    try:
        from src.services.core.metasell_conversion import MetaSellConversionEngine

        window = max(1, min(int(days or 30), 365))
        engine = MetaSellConversionEngine(db=api_state.db_instance)
        cards = await engine.generate_seller_cards(days=window)
        wanted = manager.strip().casefold()
        for name, card in cards:
            if name.casefold() == wanted:
                return {"manager_name": name, "card": card, "days": window}
        return JSONResponse(
            status_code=404,
            content={
                "error": "manager_not_found",
                "hint": "Oxirgi davrda shu menejerga bog'langan baholangan qo'ng'iroq yo'q",
                "available": [name for name, _ in cards],
            },
        )
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("conversion_seller_card", exc)


@router.post("/process-call")
async def ai_process_call(request: Request):
    """Qo'ng'iroqni tahlil qilib, natijasini qaytaradi."""
    if not _secret_check(request):
        return _unauthorized()
    try:
        data = await request.json()
        call_id = str(data.get("call_id") or "").strip()
        if not call_id:
            return JSONResponse(
                status_code=400, content={"error": "call_id is required"}
            )

        from src.services.ai.conversation_engine import (
            CallRecord,
            get_conversation_engine,
        )

        record = CallRecord(
            call_id=call_id,
            lead_id=int(data.get("lead_id") or 0),
            manager_id=int(data.get("manager_id") or 0),
            manager_name=str(data.get("manager_name") or ""),
            started_at=datetime.now(timezone.utc),
            duration_seconds=int(data.get("duration_seconds") or 0),
            audio_url=data.get("audio_url"),
            transcript=str(data.get("transcript") or ""),
        )
        engine = get_conversation_engine(
            amocrm_client=api_state.amocrm_instance,
            db_pool=api_state.db_instance,
        )
        analysis = await engine.process_call(record)
        if analysis is None:
            return JSONResponse(
                status_code=422,
                content={"error": "analysis_failed", "call_id": call_id},
            )
        return analysis.to_dict()
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("ai_process_call", exc)


@router.get("/deal-hygiene")
async def ai_deal_hygiene(limit: int = 100):
    """AmoCRM bitimlari gigiyenasi bo'yicha audit hisoboti."""
    if api_state.amocrm_instance is None:
        return _unavailable("ai_deal_hygiene", "amocrm_not_connected")
    try:
        from src.services.core.deal_hygiene import AmoCRMDealHygieneAgent

        agent = AmoCRMDealHygieneAgent(
            amocrm=api_state.amocrm_instance, db=api_state.db_instance
        )
        return await agent.audit(limit=limit)
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("ai_deal_hygiene", exc)


@router.post("/deal-hygiene/apply")
async def ai_deal_hygiene_apply(request: Request):
    """Auditni bajaradi va topilgan muammolar bo'yicha vazifa yaratadi."""
    if not _secret_check(request):
        return _unauthorized()
    if api_state.amocrm_instance is None:
        return _unavailable("ai_deal_hygiene_apply", "amocrm_not_connected")
    try:
        data: Dict[str, Any] = {}
        try:
            data = await request.json()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            pass  # bo'sh tana — standart qiymatlar bilan ishlaymiz

        from src.services.core.deal_hygiene import AmoCRMDealHygieneAgent

        agent = AmoCRMDealHygieneAgent(
            amocrm=api_state.amocrm_instance, db=api_state.db_instance
        )
        report = await agent.audit(limit=int(data.get("limit") or 100))
        return await agent.apply_report(
            report, create_tasks=bool(data.get("create_tasks", True))
        )
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("ai_deal_hygiene_apply", exc)


def _build_lead_classifier() -> Optional[Any]:
    """LeadClassifier — AmoCRM va Gemini kaliti bo'lsagina quriladi."""
    if api_state.amocrm_instance is None:
        return None
    # `GEMINI_API_KEY` — Pydantic SecretStr. O'ramni uzatib bo'lmaydi:
    # `genai.Client` niqoblangan qiymat oladi va autentifikatsiya yiqiladi.
    raw_key = getattr(settings, "GEMINI_API_KEY", "")
    if hasattr(raw_key, "get_secret_value"):
        gemini_key = raw_key.get_secret_value() or ""
    else:
        gemini_key = str(raw_key or "")
    if not gemini_key.strip():
        return None

    from src.services.core.leads.lead_classifier import LeadClassifier

    return LeadClassifier(amocrm=api_state.amocrm_instance, gemini_api_key=gemini_key)


@router.post("/lead-classifier/tag")
async def ai_lead_classifier_tag(request: Request):
    """Bitta leadni klassifikatsiya qiladi."""
    if not _secret_check(request):
        return _unauthorized()
    try:
        data = await request.json()
        lead_id = data.get("lead_id")
        if not lead_id:
            return JSONResponse(
                status_code=400, content={"error": "lead_id is required"}
            )

        classifier = _build_lead_classifier()
        if classifier is None:
            return _unavailable(
                "ai_lead_classifier_tag", "amocrm_or_gemini_key_missing"
            )

        # `classify_lead` lead obyektini kutadi, id emas.
        lead = await api_state.amocrm_instance.get_lead(int(lead_id))
        if not lead:
            return JSONResponse(
                status_code=404,
                content={"error": "lead_not_found", "lead_id": lead_id},
            )

        result = await classifier.classify_lead(lead)
        if result is None:
            return JSONResponse(
                status_code=422,
                content={"error": "classification_failed", "lead_id": lead_id},
            )

        payload = asdict(result)
        # `category` — Enum, JSON uchun qiymatga aylantiramiz.
        payload["category"] = result.category.value
        return payload
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _fail("ai_lead_classifier_tag", exc)
