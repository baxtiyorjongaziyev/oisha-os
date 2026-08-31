"""
Keyword-based rule assessment for NegotiationEngine fallback.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.agents.negotiation.models import NegotiationAssessment


def _detect_objections(msg: str) -> tuple[str, List[str]]:
    risk_flags: List[str] = []
    if any(w in msg for w in ["qimmat", "narx", "chegirma", "discount", "budget", "arzon"]):
        risk_flags.append("price_pressure")
        return "price", risk_flags
    if any(w in msg for w in ["portfolio", "ishlar", "case", "garant", "ishonch", "tajriba"]):
        return "trust", risk_flags
    if any(w in msg for w in ["keyin", "vaqt", "hozir emas", "kechroq", "keyinroq"]):
        return "timing", risk_flags
    if any(w in msg for w in ["raqobatchi", "boshqa agentlik", "arzonroq", "taqqos"]):
        risk_flags.append("competitive_pressure")
        return "competition", risk_flags
    if any(w in msg for w in ["shartnoma", "nda", "akt", "kpi", "yuridik", "legal", "advokat"]):
        risk_flags.append("legal_review")
        return "legal", risk_flags
    if any(w in msg for w in ["byudjet", "mablag", "pul yo'q", "moliya"]):
        risk_flags.append("budget_constraint")
        return "budget", risk_flags
    if any(w in msg for w in ["kerak emas", "bekor", "qiziq emas", "yoqmadi"]):
        risk_flags.append("high_churn_risk")
        return "no_need", risk_flags
    return "none", risk_flags


def _detect_intent(msg: str, objection: str) -> tuple[str, float]:
    if any(w in msg for w in ["narx", "qancha", "narxi", "narxlar", "summa", "dollar"]):
        return "pricing", 0.6
    if any(w in msg for w in ["boshlaymiz", "hisob", "to'lov", "shartnoma yubor", "roziman"]):
        return "ready_to_close", 0.9
    if any(w in msg for w in ["uchrashuv", "zoom", "ko'rishaylik", "call"]):
        return "request_meeting", 0.75
    if any(w in msg for w in ["taklif", "kpra", "prezentatsiya", "variant"]):
        return "request_proposal", 0.65
    if objection in ("price", "competition", "budget"):
        return "bargaining", 0.45
    if objection in ("trust", "timing", "legal"):
        return "evaluating", 0.4
    if objection == "no_need":
        return "disinterested", 0.1
    return "exploring", 0.5


def _detect_stage(crm: str, intent: str, msg: str) -> str:
    if "shartnoma" in crm or intent == "ready_to_close":
        return "closing"
    if "uchrashuv" in crm or intent == "request_meeting":
        return "meeting"
    if "taklif" in crm or intent == "request_proposal":
        return "proposal"
    if any(w in msg for w in ["qanday", "nima", "qancha", "xizmatlar"]):
        return "discovery"
    return "qualifying"


def _determine_tactic(objection: str, intent: str, stage: str) -> str:
    if intent == "ready_to_close":
        return "assumptive_close"
    if objection == "price":
        return "value_reframe"
    if objection == "trust":
        return "social_proof"
    if objection == "timing":
        return "urgency_ethical"
    if objection == "competition":
        return "differentiation_focus"
    if objection == "budget":
        return "scope_down"
    if stage == "meeting":
        return "calendar_commit"
    return "diagnostic_questioning"


class NegotiationRuleMixin:
    """Synchronous keyword and pattern-based assessment."""

    @staticmethod
    def assess(
        message: str,
        crm_status: str = "",
        *,
        autonomy_mode: str = "autonomous",
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> NegotiationAssessment:
        """Fast keyword-based fallback. Still reliable for common patterns."""
        del history, context
        msg = (message or "").lower()
        crm = (crm_status or "").lower()

        objection, risk_flags = _detect_objections(msg)
        intent, intent_score = _detect_intent(msg, objection)
        stage = _detect_stage(crm, intent, msg)
        tactic = _determine_tactic(objection, intent, stage)

        return NegotiationAssessment(
            stage=stage,
            intent=intent,
            objection=objection,
            urgency="medium",
            sentiment="neutral",
            close_probability=intent_score,
            autonomy_mode=autonomy_mode,
            recommended_status="in_progress",
            next_action=tactic,
            approval_needed=False,
            risk_flags=risk_flags,
            autonomous_mission=f"Rule engine mapped '{objection}' objection at '{stage}' stage to '{tactic}'",
        )
