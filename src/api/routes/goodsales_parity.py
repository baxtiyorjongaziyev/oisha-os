"""GoodSales Parity API Routes.

Exposes REST endpoints for the complete GoodSales operational parity suite:
NextSteps reverse funnel & 18-action priority queue, 1:1 coaching dossiers & printable sheets,
Telegram daily brief dispatch, AI voice exam simulation, and compensation/davomat matrix.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.services.command_center.next_steps_engine import (
    NextStepsEngine, PlanTarget, FunnelMath, TeamPulse, ActionItem,
)
from src.services.command_center.one_on_one import OneOnOneCoachService, OneOnOneDossier
from src.services.proactive.daily_brief import DailyBriefService, ManagerDailyBrief
from src.services.ai.voice_exam import VoiceExamEngine, VoiceExamSession
from src.services.command_center.compensation_davomat import (
    CompensationDavomatEngine, CompensationCalculation,
)

router = APIRouter(prefix="/api", tags=["goodsales-parity"])

_next_steps_engine = NextStepsEngine()
_one_on_one_service = OneOnOneCoachService()
_daily_brief_service = DailyBriefService()
_voice_exam_engine = VoiceExamEngine()
_compensation_engine = CompensationDavomatEngine()

_exam_sessions: Dict[str, VoiceExamSession] = {}

_SAMPLE_MANAGERS: List[Dict[str, Any]] = [
    {
        "id": "mgr_51", "name": "Kamola Karimova", "role": "Senior Closer", "has_telegram": True,
        "telegram_chat_id": "998901234567", "fact": 369_740_000, "plan": 150_000_000, "plan_percent": 246,
        "target": 396_000_000, "conv": 16.8, "score": 65.0, "hot_deals_sum": 588_900_000,
        "hot_deals_count": 90, "overdue_calls": 120, "overdue_tasks": 25, "focus_skill": "Yakunlash va keyingi qadam",
        "skill_score": 50, "level": 4, "level_title": "Kuchli", "talk_minutes": 2100, "calls_count": 520,
        "work_days": 22, "late_minutes": 10, "absent_days": 0,
    },
    {
        "id": "mgr_52", "name": "Mohira Karimova", "role": "Closer", "has_telegram": True,
        "telegram_chat_id": "998901234568", "fact": 212_400_000, "plan": 200_000_000, "plan_percent": 106,
        "target": 227_500_000, "conv": 10.7, "score": 64.0, "hot_deals_sum": 57_500_000,
        "hot_deals_count": 45, "overdue_calls": 50, "overdue_tasks": 10, "focus_skill": "Yakunlash va keyingi qadam",
        "skill_score": 57, "level": 4, "level_title": "Kuchli", "talk_minutes": 1850, "calls_count": 410,
        "work_days": 22, "late_minutes": 15, "absent_days": 0,
    },
    {
        "id": "mgr_53", "name": "Feruza Karimova", "role": "Account Exec", "has_telegram": True,
        "telegram_chat_id": "998901234569", "fact": 22_800_000, "plan": 50_000_000, "plan_percent": 46,
        "target": 26_500_000, "conv": 3.0, "score": 58.0, "hot_deals_sum": 22_000_000,
        "hot_deals_count": 15, "overdue_calls": 30, "overdue_tasks": 15, "focus_skill": "Yakunlash va keyingi qadam",
        "skill_score": 50, "level": 2, "level_title": "Oʻsishda", "talk_minutes": 1400, "calls_count": 320,
        "work_days": 21, "late_minutes": 40, "absent_days": 1,
    },
    {
        "id": "mgr_54", "name": "Eldor Karimov", "role": "Junior SDR", "has_telegram": False,
        "telegram_chat_id": None, "fact": 0, "plan": 50_000_000, "plan_percent": 0, "target": 5_500_000,
        "conv": 0.0, "score": 44.0, "hot_deals_sum": 12_400_000, "hot_deals_count": 6, "overdue_calls": 15,
        "overdue_tasks": 8, "focus_skill": "Salomlashish va kontakt", "skill_score": 46, "level": 1,
        "level_title": "Boshlangʻich", "talk_minutes": 550, "calls_count": 110, "work_days": 20,
        "late_minutes": 65, "absent_days": 2,
    },
]

class BriefSendRequest(BaseModel):
    manager_ids: Optional[List[str]] = Field(default=None, alias="managerIds")

class StartExamRequest(BaseModel):
    manager_id: str
    scenario_id: str = "pre_sale_1"

class ExamTurnRequest(BaseModel):
    session_id: str
    manager_text: str

class FinalizeExamRequest(BaseModel):
    session_id: str

@router.get("/next-steps")
async def get_next_steps_payload() -> Dict[str, Any]:
    """Return full operational payload matching GoodSales next-steps view."""
    target_amount, current_fact, avg_check = 694_000_000, 623_700_000, 2_700_000
    conv_rate, kval_rate = 0.067, 0.449

    funnel_calc = _next_steps_engine.compute_funnel(target_amount, avg_check, conv_rate, kval_rate)
    team_pulse = _next_steps_engine.aggregate_team_pulse(_SAMPLE_MANAGERS)
    actions = _next_steps_engine.generate_action_queue(target_amount, current_fact, _SAMPLE_MANAGERS, avg_check, conv_rate * 100)

    lost_breakdown = [
        {"reason": "Vaqti toʻgʻri kelmadi", "count": 453, "type": "sales_process"},
        {"reason": "Telefonni koʻtarmadi", "count": 232, "type": "sales_process"},
        {"reason": "Murojaat qoldirmagan", "count": 881, "type": "lead_quality"},
        {"reason": "Dubl", "count": 878, "type": "lead_quality"},
        {"reason": "Sabab yozilmagan", "count": 1043, "type": "no_reason"},
    ]
    lost_analysis = _next_steps_engine.analyze_lost_revenue(lost_breakdown, avg_check=avg_check)

    sources_data = [
        {"name": "Sayt formasi", "leads": 7945, "kval": 3766, "won": 643, "revenue": 897_000_000},
        {"name": "Kiruvchi qoʻngʻiroq", "leads": 2488, "kval": 865, "won": 492, "revenue": 383_000_000},
        {"name": "Instagram Direct", "leads": 1563, "kval": 403, "won": 15, "revenue": 3_126_000},
        {"name": "Baza", "leads": 2313, "kval": 1556, "won": 502, "revenue": 902_000_000},
    ]
    sources_attributions = _next_steps_engine.attribute_sources(sources_data)

    managers_summary = []
    for m in _SAMPLE_MANAGERS:
        dossier = _one_on_one_service.build_dossier(m)
        brief = _daily_brief_service.prepare_brief(m)
        managers_summary.append({
            "id": m["id"], "name": m["name"], "role": m.get("role", "Menejer"),
            "hasTelegram": m["has_telegram"], "conv": m["conv"], "score": m["score"],
            "plan": {"fact": m["fact"], "plan": m["plan"], "percent": m["plan_percent"]},
            "level": {"level": dossier.level.level, "title": dossier.level.title, "index": dossier.level.index},
            "oneOnOne": {"wins": dossier.wins, "concerns": dossier.concerns, "commitments": dossier.commitments, "questions": dossier.questions},
            "brief": brief.brief_text,
        })

    return {
        "success": True,
        "data": {
            "scope": "company", "mode": "amount", "phase": "month_close",
            "monthKey": "2026-07", "nextMonthKey": "2026-08",
            "plan": {"plan": 650_000_000, "fact": current_fact, "percent": 96, "target": target_amount, "avgCheck": avg_check},
            "funnel": {"sales": funnel_calc.sales_needed, "kval": funnel_calc.kval_leads_needed, "leads": funnel_calc.total_leads_needed, "conv": funnel_calc.conv_rate * 100, "kvalRate": funnel_calc.kval_rate * 100},
            "team": {"conv": team_pulse.conv_rate_90d, "topConvName": team_pulse.top_conv_manager, "avgScore": team_pulse.avg_ai_score, "hotDealsSum": team_pulse.hot_deals_sum, "hotDealsCount": team_pulse.hot_deals_count, "overdueCalls": team_pulse.overdue_promises_count, "overdueTasks": team_pulse.overdue_tasks_count},
            "actions": [{"id": a.id, "kind": a.kind, "priority": a.priority, "short": a.short, "title": a.title, "detail": a.detail, "impact": a.impact, "impactNote": a.impact_note, "href": a.href, "managerName": a.manager_name} for a in actions],
            "managers": managers_summary,
            "lost": {k: {"count": v.deals_count, "pct": v.pct, "recoverableSum": v.recoverable_sum, "note": v.note} for k, v in lost_analysis.items()},
            "sources": [{"source": s.source_name, "leads": s.leads_count, "kvalPct": s.kval_pct, "convPct": s.conv_pct, "revPerLead": s.rev_per_lead, "junkPct": s.junk_pct, "recommendation": s.recommendation} for s in sources_attributions],
        },
    }

@router.post("/next-steps/brief/send")
async def send_daily_briefs(req: Optional[BriefSendRequest] = None) -> Dict[str, Any]:
    """Dispatch daily briefs to managers via Telegram."""
    selected_ids = set(req.manager_ids) if (req and req.manager_ids) else None
    targets = [m for m in _SAMPLE_MANAGERS if (not selected_ids or m["id"] in selected_ids)]
    briefs = _daily_brief_service.prepare_bulk_briefs(targets)
    result = _daily_brief_service.dispatch_briefs(briefs)
    return {"success": True, "data": {"sent": result["sent"], "skipped": result["skipped"], "failed": result["failed"], "total": result["total"]}}

@router.get("/next-steps/1on1/{manager_id}")
async def get_manager_one_on_one(manager_id: str) -> Dict[str, Any]:
    """Return structured 1:1 dossier for manager."""
    mgr = next((m for m in _SAMPLE_MANAGERS if m["id"] == manager_id), None)
    if not mgr:
        raise HTTPException(status_code=404, detail="Menejer topilmadi")
    dossier = _one_on_one_service.build_dossier(mgr)
    return {
        "success": True,
        "data": {
            "managerId": dossier.manager_id, "managerName": dossier.manager_name,
            "level": {"level": dossier.level.level, "title": dossier.level.title, "index": dossier.level.index},
            "wins": dossier.wins, "concerns": dossier.concerns, "focusSkill": dossier.focus_skill,
            "commitments": dossier.commitments, "questions": dossier.questions, "kpis": dossier.kpis,
        },
    }

@router.get("/next-steps/1on1/{manager_id}/print", response_class=HTMLResponse)
async def print_manager_one_on_one(manager_id: str) -> HTMLResponse:
    """Return printable standalone HTML sheet for manager one-on-one meeting."""
    mgr = next((m for m in _SAMPLE_MANAGERS if m["id"] == manager_id), None)
    if not mgr:
        return HTMLResponse("<h3>Menejer topilmadi</h3>", status_code=404)
    dossier = _one_on_one_service.build_dossier(mgr)
    return HTMLResponse(content=_one_on_one_service.to_printable_html(dossier))

@router.get("/voice-exam/scenarios")
async def get_voice_exam_scenarios() -> Dict[str, Any]:
    """List available voice exam scenarios."""
    scenarios = _voice_exam_engine.get_scenarios()
    return {
        "success": True,
        "scenarios": [{"id": sc.scenario_id, "title": sc.title, "clientName": sc.client_name, "difficulty": sc.difficulty, "primaryObjection": sc.primary_objection} for sc in scenarios],
    }

@router.post("/voice-exam/start")
async def start_voice_exam(req: StartExamRequest) -> Dict[str, Any]:
    """Start an interactive voice exam simulation session."""
    session = _voice_exam_engine.start_exam(req.manager_id, req.scenario_id)
    _exam_sessions[session.session_id] = session
    return {"success": True, "session_id": session.session_id, "status": session.status, "first_turn": session.turns[0].text if session.turns else ""}

@router.post("/voice-exam/turn")
async def process_voice_exam_turn(req: ExamTurnRequest) -> Dict[str, Any]:
    """Process verbal or text turn in voice exam."""
    session = _exam_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Imtihon sessiyasi topilmadi")
    res = _voice_exam_engine.process_turn(session, req.manager_text)
    return {"success": True, "data": res}

@router.post("/voice-exam/finalize")
async def finalize_voice_exam(req: FinalizeExamRequest) -> Dict[str, Any]:
    """Grade and finalize voice exam session."""
    session = _exam_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Imtihon sessiyasi topilmadi")
    final = _voice_exam_engine.finalize_exam(session)
    return {
        "success": True,
        "data": {
            "session_id": final.session_id, "overall_score": final.overall_score, "passed": final.passed,
            "criterion_scores": final.criterion_scores, "certificate_id": final.certificate_id, "feedback": final.feedback,
        },
    }

@router.get("/compensation-davomat")
async def get_compensation_davomat_matrix() -> Dict[str, Any]:
    """Return payroll compensation and attendance matrix."""
    matrix = _compensation_engine.compute_team_matrix(_SAMPLE_MANAGERS)
    return {
        "success": True,
        "data": [
            {
                "managerId": c.manager_id, "managerName": c.manager_name, "baseSalary": c.base_salary,
                "talkBonus": c.talk_bonus, "qualityBonus": c.quality_bonus, "crmBonus": c.crm_bonus,
                "salesBonus": c.sales_kpi_bonus, "latePenalty": c.late_penalty, "netSalary": c.net_salary,
            }
            for c in matrix
        ],
    }
