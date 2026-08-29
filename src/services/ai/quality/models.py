"""
Quality metric models, score breakdowns, and conversation analysis dataclasses.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("QualityAnalyzer")

SCORING_METHOD_AI = "gemini"
SCORING_METHOD_HEURISTIC = "keyword_heuristic"
OUTCOME_NOT_SALES = "not_sales"
CATEGORY_NOT_SALES = "not_sales"
_GEMINI_MODEL = "gemini-1.5-flash"

_LLM_METRICS = (
    "introduction",
    "need_identification",
    "value_proposition",
    "objection_handling",
    "closing",
    "follow_up",
    "tone",
    "active_listening",
    "question_quality",
)

def _clamp_score(value: Any) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


def _as_str_list(value: Any, limit: int = 10) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _parse_llm_scores(raw: str) -> Optional[Dict[str, Any]]:
    """LLM javobini ishonchli dict'ga aylantiradi.

    Model markdown blok yoki atrofida matn qaytarishi mumkin — shuni tozalaymiz.
    Ballar hech qachon 0-100 dan chiqmaydi.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None

    raw_scores = data.get("metric_scores")
    if not isinstance(raw_scores, dict):
        return None

    metric_scores = {m: _clamp_score(raw_scores.get(m)) for m in _LLM_METRICS}
    return {
        "metric_scores": metric_scores,
        "summary": str(data.get("summary") or "").strip(),
        "strengths": _as_str_list(data.get("strengths")),
        "weaknesses": _as_str_list(data.get("weaknesses")),
        "client_mood": str(data.get("client_mood") or "neutral").strip(),
        "client_interest_level": _clamp_score(data.get("client_interest_level")),
        "objections": _as_str_list(data.get("objections")),
        "outcome": str(data.get("outcome") or "unknown").strip(),
        "next_steps": _as_str_list(data.get("next_steps")),
    }

class QualityMetric(Enum):
    """Sifat ko'rsatkichlari."""

    INTRODUCTION = "introduction"  # O'zini tanishtirish
    NEED_IDENTIFICATION = "need_identification"  # Ehtiyoj aniqlash
    OBJECTION_HANDLING = "objection_handling"  # E'tirozlarni yengish
    VALUE_PROPOSITION = "value_proposition"  # Qiymat tushuntirish
    CLOSING = "closing"  # Yopish
    FOLLOW_UP = "follow_up"  # Keyingi qadam
    TONE = "tone"  # Ohang
    ACTIVE_LISTENING = "active_listening"  # Faql eshitish
    QUESTION_QUALITY = "question_quality"  # Savollar sifati
    TALK_RATIO = "talk_ratio"  # Mijoz/sotuvchi gapirish nisbati


@dataclass
class ScoreBreakdown:
    """Batafsil ball tahlili."""

    metric: QualityMetric
    score: int  # 0-100
    weight: float  # 0.0-1.0
    feedback: str
    examples: List[str] = field(default_factory=list)
    improvement_tips: List[str] = field(default_factory=list)


@dataclass
class ConversationAnalysis:
    """Suhbat tahlili natijalari."""

    conversation_id: str
    lead_id: Optional[int]
    manager_id: Optional[int]
    manager_name: str
    duration_seconds: int
    overall_score: int  # 0-100
    category: str  # "excellent", "good", "average", "poor", "critical"

    # Batafsil ballar
    scores: List[ScoreBreakdown] = field(default_factory=list)

    # Tahlil
    summary: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    # Gapirish nisbati
    talk_ratio_client: int = 0  # Mijoz gapirish ulushi (%)
    talk_ratio_agent: int = 0   # Sotuvchi gapirish ulushi (%)

    # Mijoz bilan bog'liq
    client_mood: str = ""  # "positive", "neutral", "negative"
    client_interest_level: int = 0  # 0-100
    objections_raised: List[str] = field(default_factory=list)

    # Natija
    outcome: str = ""  # "sale", "follow_up", "lost", "callback"
    next_steps: List[str] = field(default_factory=list)

    # Vazifalar
    recommended_tasks: List[Dict[str, Any]] = field(default_factory=list)

    # Ball qanday qo'yilgani: "gemini" yoki "keyword_heuristic".
    # Mijoz/dashboard bu farqni ko'rishi shart.
    scoring_method: str = SCORING_METHOD_HEURISTIC

    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Dict formatga o'tkazish."""
        return {
            "conversation_id": self.conversation_id,
            "lead_id": self.lead_id,
            "manager_id": self.manager_id,
            "manager_name": self.manager_name,
            "duration_seconds": self.duration_seconds,
            "overall_score": self.overall_score,
            "category": self.category,
            "scores": [
                {
                    "metric": s.metric.value,
                    "score": s.score,
                    "weight": s.weight,
                    "feedback": s.feedback,
                    "examples": s.examples,
                    "improvement_tips": s.improvement_tips,
                }
                for s in self.scores
            ],
            "summary": self.summary,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "talk_ratio_client": self.talk_ratio_client,
            "talk_ratio_agent": self.talk_ratio_agent,
            "client_mood": self.client_mood,
            "client_interest_level": self.client_interest_level,
            "objections_raised": self.objections_raised,
            "outcome": self.outcome,
            "next_steps": self.next_steps,
            "recommended_tasks": self.recommended_tasks,
            "scoring_method": self.scoring_method,
            "analyzed_at": self.analyzed_at.isoformat(),
        }

