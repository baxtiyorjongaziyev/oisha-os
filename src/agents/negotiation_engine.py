from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NegotiationAssessment:
    stage: str
    intent: str
    objection: str
    urgency: str
    sentiment: str
    close_probability: float
    autonomy_mode: str
    recommended_status: str
    next_action: str
    approval_needed: bool
    risk_flags: List[str] = field(default_factory=list)

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


class NegotiationEngine:
    @staticmethod
    def assess(
        message: str,
        crm_status: str = "",
        *,
        autonomy_mode: str = "autonomous",
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> NegotiationAssessment:
        del history, context

        msg = (message or "").lower()
        crm = (crm_status or "").lower()
        risk_flags: List[str] = []

        objection = "none"
        if any(word in msg for word in ["qimmat", "narx", "chegirma", "discount", "budget"]):
            objection = "price"
            risk_flags.append("price_pressure")
        elif any(word in msg for word in ["portfolio", "ishlar", "case", "garant", "ishonch"]):
            objection = "trust"
        elif any(word in msg for word in ["keyin", "vaqt", "hozir emas", "kechroq"]):
            objection = "timing"
        elif any(word in msg for word in ["raqobatchi", "boshqa agentlik", "arzonroq", "taqqos"]):
            objection = "competition"
            risk_flags.append("competitive_pressure")
        elif any(word in msg for word in ["shartnoma", "nda", "akt", "kpi", "yuridik", "legal"]):
            objection = "legal"
            risk_flags.append("legal_review")

        if any(word in msg for word in ["jahlim chiqdi", "yomon", "norozi", "muammo", "ishonmayman"]):
            sentiment = "negative"
            risk_flags.append("negative_sentiment")
        elif any(word in msg for word in ["zo'r", "yoqdi", "qiziq", "maqul"]):
            sentiment = "positive"
        else:
            sentiment = "neutral"

        urgency = "normal"
        if any(word in msg for word in ["tez", "bugun", "ertaga", "shoshilinch", "deadline"]):
            urgency = "high"
        elif any(word in msg for word in ["keyinroq", "vaqt bor", "shoshilmaymiz"]):
            urgency = "low"

        intent = "qualify"
        if any(word in msg for word in ["narx", "qancha", "budget", "chegirma"]):
            intent = "pricing"
        elif any(word in msg for word in ["uchrashuv", "qo'ng'iroq", "call", "zoom", "meeting"]):
            intent = "meeting"
        elif any(word in msg for word in ["tayyor", "boshlaymiz", "start", "to'laymiz", "shartnoma"]):
            intent = "closing"
        elif any(word in msg for word in ["portfolio", "case", "misol", "ishlaringiz"]):
            intent = "proof"
        elif any(word in msg for word in ["keyin", "o'ylab", "o'ylab ko'raman"]):
            intent = "nurture"

        stage = "new_lead"
        if "meeting" in crm or intent == "meeting":
            stage = "meeting_ready"
        elif "qualified" in crm or "interested" in crm or intent in {"pricing", "proof"}:
            stage = "qualified"
        elif "won" in crm or "success" in crm or intent == "closing":
            stage = "closing"

        recommended_status_map = {
            "new_lead": "Initial Contact",
            "qualified": "Interested",
            "meeting_ready": "Meeting Scheduled",
            "closing": "Qualified",
        }
        recommended_status = recommended_status_map.get(stage, "Initial Contact")

        next_action = "qualify_need"
        if intent == "pricing":
            next_action = "value_anchor"
        elif intent == "proof":
            next_action = "show_relevant_case"
        elif intent == "meeting":
            next_action = "schedule_strategy_session"
        elif intent == "closing":
            next_action = "confirm_scope_and_close"
        elif intent == "nurture":
            next_action = "create_followup_commitment"

        probability = 0.35
        if stage == "qualified":
            probability += 0.2
        if stage == "meeting_ready":
            probability += 0.3
        if intent == "closing":
            probability += 0.2
        if sentiment == "positive":
            probability += 0.1
        if objection in {"price", "competition", "legal"}:
            probability -= 0.15
        if "negative_sentiment" in risk_flags:
            probability -= 0.2
        close_probability = max(0.05, min(0.95, probability))

        approval_needed = any(flag in risk_flags for flag in ["legal_review", "competitive_pressure", "negative_sentiment"])
        if objection == "price" and any(word in msg for word in ["chegirma", "discount"]):
            approval_needed = True
            risk_flags.append("discount_request")

        return NegotiationAssessment(
            stage=stage,
            intent=intent,
            objection=objection,
            urgency=urgency,
            sentiment=sentiment,
            close_probability=round(close_probability, 2),
            autonomy_mode=autonomy_mode,
            recommended_status=recommended_status,
            next_action=next_action,
            approval_needed=approval_needed,
            risk_flags=risk_flags,
        )
