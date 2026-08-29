"""
Data models and conversion trend structures for MetaSell Analytics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from src.services.core.metasell.constants import STAGE_LABELS_UZ, STAGE_DRILLS_UZ


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return getattr(row, key, default)
    except Exception:
        return default


def _json_obj(val: Any) -> Dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def _json_list(val: Any) -> List[Any]:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0

@dataclass
class StageGap:
    """Bitta bosqich bo'yicha konvertirlangan/konvertirlanmagan farqi."""

    stage: str
    won_avg: float
    lost_avg: float
    gap: float
    weighted_gap: float

    @property
    def label(self) -> str:
        return STAGE_LABELS_UZ.get(self.stage, self.stage)


@dataclass
class ConversionTrend:
    """Joriy davr va oldingi davr konversiyasi.

    Reklamadagi "+28% ↗" aynan shu. Farq FOIZ PUNKTIDA (pp) beriladi,
    nisbiy foizda emas: 20% dan 25% ga o'sish — bu +5 pp. Nisbiy "+25%"
    deb yozish bir xil ma'lumotni kattaroq ko'rsatadi va chalg'itadi.
    """

    days: int
    current_rate: float
    previous_rate: float
    current_calls: int
    previous_calls: int
    reliable: bool
    reason: str = ""

    @property
    def delta_pp(self) -> float:
        return self.current_rate - self.previous_rate

    @property
    def direction(self) -> str:
        if not self.reliable:
            return "noaniq"
        if self.delta_pp > 1:
            return "o'smoqda"
        if self.delta_pp < -1:
            return "pasaymoqda"
        return "barqaror"

    @property
    def arrow(self) -> str:
        return {"o'smoqda": "↗", "pasaymoqda": "↘"}.get(self.direction, "→")

    def headline(self) -> str:
        """Dashboard uchun bitta qator."""
        if not self.reliable:
            return f"Konversiya: {self.current_rate:.0f}% (trend: {self.reason})"
        sign = "+" if self.delta_pp >= 0 else ""
        return (
            f"Konversiya: {self.current_rate:.0f}% "
            f"({sign}{self.delta_pp:.0f} pp {self.arrow} oldingi {self.days} kunga nisbatan)"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "days": self.days,
            "current_rate": round(self.current_rate, 1),
            "previous_rate": round(self.previous_rate, 1),
            "delta_pp": round(self.delta_pp, 1),
            "direction": self.direction,
            "current_calls": self.current_calls,
            "previous_calls": self.previous_calls,
            "reliable": self.reliable,
            "reason": self.reason,
            "headline": self.headline(),
        }


@dataclass
class SellerDiagnosis:
    """Bitta sotuvchining konversiya diagnozi."""

    manager_name: str
    total_calls: int
    converted_calls: int
    conversion_rate: float
    avg_score: float
    growth_stage: Optional[str] = None
    growth_gap: Optional[StageGap] = None
    top_weaknesses: List[str] = field(default_factory=list)
    top_objections: List[str] = field(default_factory=list)
    projected_lift: float = 0.0
    reason: str = ""
    # Pul — `metasell_revenue.aggregate_revenue` orqali, bitim bo'yicha
    # yagonalangan (bir bitimga bir nechta qo'ng'iroq bo'lishi mumkin).
    revenue_won: float = 0.0
    revenue_at_risk: float = 0.0
    deals_won: int = 0
    deals_lost: int = 0

    @property
    def has_diagnosis(self) -> bool:
        return self.growth_stage is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_name": self.manager_name,
            "total_calls": self.total_calls,
            "converted_calls": self.converted_calls,
            "conversion_rate": round(self.conversion_rate, 1),
            "avg_score": round(self.avg_score, 1),
            "growth_stage": self.growth_stage,
            "growth_stage_label": (
                STAGE_LABELS_UZ.get(self.growth_stage, "") if self.growth_stage else ""
            ),
            "growth_gap": round(self.growth_gap.gap, 1) if self.growth_gap else None,
            "drill": (
                STAGE_DRILLS_UZ.get(self.growth_stage, "") if self.growth_stage else ""
            ),
            "top_weaknesses": self.top_weaknesses,
            "top_objections": self.top_objections,
            "projected_lift": round(self.projected_lift, 1),
            "has_diagnosis": self.has_diagnosis,
            "reason": self.reason,
            "revenue_won": round(self.revenue_won),
            "revenue_at_risk": round(self.revenue_at_risk),
            "deals_won": self.deals_won,
            "deals_lost": self.deals_lost,
        }
