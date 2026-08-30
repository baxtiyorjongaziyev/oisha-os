"""
Data models for Call Analytics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DailyStats:
    """Kunlik statistika."""

    date: str
    total_calls: int = 0
    analyzed_calls: int = 0
    average_score: float = 0.0
    total_duration: int = 0

    sales_made: int = 0
    follow_ups: int = 0
    lost: int = 0
    callbacks: int = 0

    peak_hour: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "total_calls": self.total_calls,
            "analyzed_calls": self.analyzed_calls,
            "average_score": round(self.average_score, 1),
            "total_duration": self.total_duration,
            "avg_duration": round(self.total_duration / max(self.total_calls, 1), 0),
            "outcomes": {
                "sales": self.sales_made,
                "follow_up": self.follow_ups,
                "lost": self.lost,
                "callback": self.callbacks,
            },
        }


@dataclass
class ManagerPerformance:
    """Manager samaradorligi."""

    manager_id: int
    manager_name: str

    total_calls: int = 0
    average_score: float = 0.0
    total_duration: int = 0

    sales_made: int = 0
    conversion_rate: float = 0.0

    skill_scores: Dict[str, float] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    areas_for_improvement: List[str] = field(default_factory=list)
    trend: str = "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "manager_name": self.manager_name,
            "total_calls": self.total_calls,
            "average_score": round(self.average_score, 1),
            "total_duration": self.total_duration,
            "sales_made": self.sales_made,
            "conversion_rate": round(self.conversion_rate, 1),
            "skill_scores": {k: round(v, 1) for k, v in self.skill_scores.items()},
            "strengths": self.strengths,
            "areas_for_improvement": self.areas_for_improvement,
            "trend": self.trend,
        }


@dataclass
class LostClientAnalysis:
    """Yo'qotilgan mijozlar tahlili."""

    total_lost: int = 0
    lost_reasons: Dict[str, int] = field(default_factory=dict)
    lost_at_stages: Dict[str, int] = field(default_factory=dict)
    unhandled_objections: Dict[str, int] = field(default_factory=dict)
    preventable_percentage: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_lost": self.total_lost,
            "lost_reasons": self.lost_reasons,
            "lost_at_stages": self.lost_at_stages,
            "unhandled_objections": self.unhandled_objections,
            "preventable_percentage": round(self.preventable_percentage, 1),
            "recommendations": self.recommendations,
        }
