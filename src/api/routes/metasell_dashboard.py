"""Oisha-OS Sales Cockpit and Executive Command Center API Routes.

Exposes REST endpoints for the full suite of in-house Oisha-OS capabilities:
Speed to Lead (SLA), Stuck Deals Radar, Marketing Ad Attribution, AI Sales Simulator,
Voice Roleplay (TTS/STT), Native WebRTC PBX Softphone, GSM SMS Gateway,
Knowledge Quizzes, and Morning Task Triage.
"""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.services.ai.audio_simulator import (
    AudioSimulatorService,
    AudioTurnRequest,
    AudioTurnResponse,
)
from src.services.ai.knowledge_quiz import (
    KnowledgeQuizEngine,
    QuizSubmission,
)
from src.services.ai.sales_simulator import (
    SalesSimulatorEngine,
    SimulationTurn,
)
from src.services.command_center.ad_attribution import (
    AdAttributionEngine,
)
from src.services.command_center.live_db_bridge import LiveDataBridge
from src.services.command_center.morning_tasks import (
    MorningTaskItem,
    MorningTriageService,
)
from src.services.command_center.speed_to_lead import (
    SpeedToLeadCalculator,
)
from src.services.command_center.stuck_deals import (
    StuckDealsRadar,
)
from src.services.telephony.unified_gateway import UnifiedTelephonyGateway

router = APIRouter(tags=["oisha-cockpit"])

_bridge = LiveDataBridge()
_simulator_engine = SalesSimulatorEngine()
_audio_simulator = AudioSimulatorService(simulator_engine=_simulator_engine)
_quiz_engine = KnowledgeQuizEngine()
_triage_service = MorningTriageService()
_telephony_gateway = UnifiedTelephonyGateway()


class SimulatorTurnRequest(BaseModel):
    """Payload for submitting a manager dialogue turn to the simulator."""

    scenario_id: str = Field(..., description="Target scenario identifier")
    manager_message: str = Field(..., description="Message spoken by the sales manager")
    history: list[dict[str, str]] = Field(default_factory=list, description="Dialogue history")


class QuizSubmitRequest(BaseModel):
    """Payload for submitting quiz answers for grading."""

    user_id: str = Field(..., description="Sales representative user id")
    answers: dict[str, str] = Field(..., description="Map of question_id to selected option")


class SmsDispatchRequest(BaseModel):
    """Payload for dispatching an SMS to a customer."""

    phone: str = Field(..., description="Recipient phone number")
    message: str = Field(..., description="SMS message text")


@router.get("/oisha-console", response_class=HTMLResponse)
@router.get("/cockpit", response_class=HTMLResponse)
@router.get("/metasell-console", response_class=HTMLResponse)
async def get_metasell_console_ui() -> HTMLResponse:
    """Render the full Oisha Cockpit interactive dashboard web interface."""
    template_path = Path(__file__).resolve().parent.parent / "templates" / "metasell_dashboard.html"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
        return HTMLResponse(content=content)
    return HTMLResponse("<h3>Oisha Cockpit Template topilmadi</h3>", status_code=404)


@router.get("/telephony/webrtc-session")
async def get_webrtc_session(
    manager_id: str = "mgr_default",
    extension: str = "101",
) -> dict[str, Any]:
    """Generate in-browser WebRTC softphone credentials (Native Oisha Voice)."""
    return _telephony_gateway.native_voice.create_webrtc_dialer_session(
        manager_id=manager_id,
        manager_extension=extension,
    )


@router.post("/sms/dispatch")
async def dispatch_sms(req: SmsDispatchRequest) -> dict[str, Any]:
    """Dispatch customer SMS via Native GSM modem with Eskiz fallback."""
    msg = await _telephony_gateway.dispatch_customer_sms(req.phone, req.message)
    return {
        "sms_id": msg.sms_id,
        "provider": msg.provider,
        "status": msg.status,
        "cost_uzs": msg.cost_uzs,
    }


@router.get("/metasell-executive")
async def get_metasell_executive_dashboard() -> dict[str, Any]:
    """Return aggregated executive dashboard for Oisha-OS Cockpit."""
    now = datetime.now(UTC)

    # 1. Fetch live data from Turso/Database bridge
    interactions = await _bridge.fetch_recent_lead_interactions()
    deal_records = await _bridge.fetch_active_deal_records()
    campaigns, ad_leads = await _bridge.fetch_ad_attribution_data()

    # 2. Compute dynamic metrics
    stl_calc = SpeedToLeadCalculator(reference_time=now, target_sla_minutes=30)
    stl_metrics = stl_calc.calculate(interactions)

    stuck_radar = StuckDealsRadar(reference_time=now, default_threshold_days=3)
    stuck_summary = stuck_radar.analyze(deal_records)

    ad_engine = AdAttributionEngine()
    ad_summary = ad_engine.calculate(campaigns, ad_leads)

    return {
        "hero": {
            "sales_won_amount": ad_summary.total_revenue,
            "sales_won_count": ad_summary.total_sales,
            "sales_lost_count": 1,
            "conversion_rate_pct": ad_summary.conversion_rate_pct,
            "vs_previous_points": 4.2,
            "top_loss_reason": "Boshqa arzonroq taklifni tanladi",
        },
        "speed_to_lead": {
            "total_leads": stl_metrics.total_leads,
            "answered_leads": stl_metrics.answered_leads,
            "unanswered_leads": stl_metrics.unanswered_leads,
            "sla_rate_pct": stl_metrics.sla_rate_pct,
            "avg_response_minutes": stl_metrics.avg_response_minutes,
            "buckets": stl_metrics.buckets,
            "channel_breakdown": stl_metrics.channel_breakdown,
            "longest_wait": (
                {
                    "customer_name": stl_metrics.longest_wait.customer_name,
                    "channel": stl_metrics.longest_wait.channel,
                    "wait_minutes": stl_metrics.longest_wait.wait_minutes,
                }
                if stl_metrics.longest_wait
                else None
            ),
        },
        "stuck_deals": {
            "total_stuck_deals": stuck_summary.total_stuck_deals,
            "total_stuck_value": stuck_summary.total_stuck_value,
            "stage_summaries": [
                {
                    "stage_id": s.stage_id,
                    "stage_name": s.stage_name,
                    "stuck_count": s.stuck_count,
                    "oldest_days": s.oldest_days,
                    "stuck_amount": s.stuck_amount,
                }
                for s in stuck_summary.stage_summaries
            ],
            "oldest_deal": (
                {
                    "deal_name": stuck_summary.oldest_deal.deal_name,
                    "stuck_days": stuck_summary.oldest_deal.stuck_days,
                    "manager_name": stuck_summary.oldest_deal.manager_name,
                }
                if stuck_summary.oldest_deal
                else None
            ),
        },
        "ad_attribution": {
            "total_spend": ad_summary.total_spend,
            "total_new_leads": ad_summary.total_new_leads,
            "cost_per_lead": ad_summary.cost_per_lead,
            "total_sales": ad_summary.total_sales,
            "cost_per_sale": ad_summary.cost_per_sale,
            "total_revenue": ad_summary.total_revenue,
            "conversion_rate_pct": ad_summary.conversion_rate_pct,
            "overall_roi_pct": ad_summary.overall_roi_pct,
        },
        "attention": {
            "waiting_customers_count": stl_metrics.unanswered_leads,
            "missed_calls_count": 2,
            "overdue_tasks_count": 3,
            "unassigned_deals_count": 1,
        },
        "team_leaderboard": [
            {
                "manager_name": "Aziz Karimov",
                "new_leads": 14,
                "won_sales": 5,
                "won_amount": 35_000_000.0,
                "conversion_pct": 35.7,
                "calls_count": 48,
                "talk_time_minutes": 112,
            },
            {
                "manager_name": "Dilnoza Rahimova",
                "new_leads": 12,
                "won_sales": 4,
                "won_amount": 26_000_000.0,
                "conversion_pct": 33.3,
                "calls_count": 41,
                "talk_time_minutes": 95,
            },
        ],
    }


@router.get("/simulator/scenarios")
async def list_simulator_scenarios() -> list[dict[str, Any]]:
    """Return all available sales simulation roleplay scenarios."""
    scenarios = _simulator_engine.get_scenarios()
    return [
        {
            "scenario_id": s.scenario_id,
            "title": s.title,
            "goal": s.goal,
            "situation": s.situation,
            "client_name": s.client_name,
            "client_gender": s.client_gender,
            "mood": s.mood,
            "what_convinces": s.what_convinces,
            "hidden_facts_count": len(s.hidden_facts),
        }
        for s in scenarios
    ]


@router.post("/simulator/turn")
async def process_simulator_turn(req: SimulatorTurnRequest) -> dict[str, Any]:
    """Execute one dialogue turn with the simulated buyer persona."""
    scenario = _simulator_engine.get_scenario(req.scenario_id)
    if not scenario:
        scenarios = _simulator_engine.get_scenarios()
        scenario = scenarios[0]

    history_turns = [
        SimulationTurn(role=h.get("role", "manager"), content=h.get("content", ""))
        for h in req.history
    ]

    result = _simulator_engine.process_manager_message(
        scenario=scenario,
        history=history_turns,
        manager_message=req.manager_message,
    )

    return {
        "client_response": result.client_response,
        "revealed_facts": result.revealed_facts,
        "coaching_tip": result.coaching_tip,
    }


@router.post("/simulator/voice-turn", response_model=AudioTurnResponse)
async def process_simulator_voice_turn(req: AudioTurnRequest) -> AudioTurnResponse:
    """Execute one voice dialogue turn with speech-to-text and text-to-speech."""
    return await _audio_simulator.process_turn(req)


@router.get("/quiz/questions")
async def list_quiz_questions() -> list[dict[str, Any]]:
    """Return multiple-choice quiz questions for sales rep knowledge testing."""
    questions = _quiz_engine.get_questions()
    return [
        {
            "question_id": q.question_id,
            "question_text": q.question_text,
            "options": q.options,
            "category": q.category,
        }
        for q in questions
    ]


@router.post("/quiz/submit")
async def submit_quiz(req: QuizSubmitRequest) -> dict[str, Any]:
    """Grade sales representative knowledge quiz submission and return feedback."""
    submission = QuizSubmission(user_id=req.user_id, answers=req.answers)
    result = _quiz_engine.grade_quiz(submission)
    return {
        "user_id": result.user_id,
        "score_pct": result.score_pct,
        "passed": result.passed,
        "correct_count": result.correct_count,
        "total_count": result.total_count,
        "category_scores": result.category_scores,
        "feedback": result.feedback,
    }


@router.get("/morning-tasks")
async def get_morning_tasks_overview() -> dict[str, Any]:
    """Return overview of morning tasks partitioned into today and overdue."""
    now = datetime.now(UTC)
    sample_tasks = [
        MorningTaskItem(
            task_id="T_101",
            lead_id="L_101",
            lead_name="Artel Korporativ",
            text="Qayta qoʻngʻiroq qilish va shartnoma holatini soʻrash",
            due_date=now.date(),
            manager_id="mgr_1",
        ),
        MorningTaskItem(
            task_id="T_102",
            lead_id="L_102",
            lead_name="Crafers Logistika",
            text="Tijoriy taklif boʻyicha uchrashuv belgilash",
            due_date=(now - timedelta(days=2)).date(),
            manager_id="mgr_1",
        ),
    ]
    overview = _triage_service.get_overview(sample_tasks)
    return {
        "today_count": overview.today_count,
        "overdue_count": overview.overdue_count,
        "today_tasks": [
            {
                "task_id": t.task_id,
                "lead_name": t.lead_name,
                "text": t.text,
                "due_date": str(t.due_date),
            }
            for t in overview.today_tasks
        ],
        "overdue_tasks": [
            {
                "task_id": t.task_id,
                "lead_name": t.lead_name,
                "text": t.text,
                "due_date": str(t.due_date),
            }
            for t in overview.overdue_tasks
        ],
    }

@router.post("/telephony/webhook/utel")
async def webhook_utel(payload: dict[str, Any]) -> dict[str, Any]:
    """Receive and normalize incoming Utel Cloud PBX call event webhook."""
    event = _telephony_gateway.process_incoming_call_webhook(provider="utel", payload=payload)
    return {"status": "ok", "call_id": event.call_id, "event": event.event_type}


@router.post("/telephony/webhook/onlinepbx")
async def webhook_onlinepbx(payload: dict[str, Any]) -> dict[str, Any]:
    """Receive and normalize incoming OnlinePBX call event webhook."""
    event = _telephony_gateway.process_incoming_call_webhook(provider="onlinepbx", payload=payload)
    return {"status": "ok", "call_id": event.call_id, "event": event.event_type}

