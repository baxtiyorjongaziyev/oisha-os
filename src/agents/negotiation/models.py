"""
Negotiation Assessment model for semantic and rule-based evaluation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


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
    pain_points: List[str] = field(default_factory=list)
    buying_signals: List[str] = field(default_factory=list)
    decision_factors: List[str] = field(default_factory=list)
    autonomous_mission: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)
