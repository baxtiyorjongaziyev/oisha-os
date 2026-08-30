"""
MetaSell Conversion Engine for aggregating scored calls, trends, and team reports.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from src.services.core.call_events import CallEventLog, aggregate_volume, team_volume
from src.services.core.metasell_revenue import aggregate_revenue
from src.services.utils.db_rows import fetch_rows
from src.services.core.metasell.constants import (
    MIN_CALLS_FOR_TREND,
    STAGE_DRILLS_UZ,
    STAGE_LABELS_UZ,
    _SELECT_RECENT_SQL,
    _SELECT_WINDOW_SQL,
)
from src.services.core.metasell.models import (
    ConversionTrend,
    SellerDiagnosis,
    _mean,
    _row_get,
)
from src.services.core.metasell.diagnostics import (
    _is_converted,
    diagnose_seller,
)
from src.services.core.metasell.cards import (
    build_seller_card,
    build_team_report,
)

logger = logging.getLogger(__name__)


class MetaSellConversionEngine:
    """`call_analyses` ustidan konversiya tahlili va sotuvchi kartochkalari."""

    def __init__(self, db: Any):
        self.db = db

    async def fetch_scored_calls(
        self, days: int = 30, offset_days: int = 0
    ) -> List[Dict[str, Any]]:
        """Baholangan savdo qo'ng'iroqlari."""
        if self.db is None:
            return []
        window_start = int(days) + int(offset_days)
        try:
            if offset_days:
                return await fetch_rows(
                    self.db,
                    _SELECT_WINDOW_SQL,
                    [f"-{window_start} days", f"-{int(offset_days)} days"],
                )
            return await fetch_rows(
                self.db, _SELECT_RECENT_SQL, [f"-{int(days)} days"]
            )
        except Exception as exc:
            logger.error("[METASELL] Qo'ng'iroqlarni o'qib bo'lmadi: %s", exc)
            return []

    async def diagnose_all(self, days: int = 30) -> List[SellerDiagnosis]:
        rows = await self.fetch_scored_calls(days)
        return self.diagnose_rows(rows)

    @staticmethod
    def diagnose_rows(rows: Sequence[Any]) -> List[SellerDiagnosis]:
        """Sotuvchilar bo'yicha diagnoz — konversiya bo'yicha saflangan."""
        by_manager: Dict[str, List[Any]] = defaultdict(list)
        for row in rows:
            name = str(_row_get(row, "manager_name", "") or "").strip()
            if not name:
                continue
            by_manager[name].append(row)

        diagnoses = [
            diagnose_seller(name, items) for name, items in by_manager.items()
        ]
        return sorted(diagnoses, key=lambda d: d.conversion_rate, reverse=True)

    @staticmethod
    def build_trend(
        current: Sequence[Any], previous: Sequence[Any], days: int
    ) -> ConversionTrend:
        """Ikki davr konversiyasini solishtiradi (sof funksiya)."""

        def rate(rows: Sequence[Any]) -> float:
            scored = [r for r in rows if int(_row_get(r, "overall_score", 0) or 0) > 0]
            if not scored:
                return 0.0
            return sum(1 for r in scored if _is_converted(r)) / len(scored) * 100

        current_n = len([r for r in current if int(_row_get(r, "overall_score", 0) or 0) > 0])
        previous_n = len([r for r in previous if int(_row_get(r, "overall_score", 0) or 0) > 0])
        reliable = current_n >= MIN_CALLS_FOR_TREND and previous_n >= MIN_CALLS_FOR_TREND
        reason = ""
        if not reliable:
            reason = (
                f"solishtirish uchun har ikki davrda {MIN_CALLS_FOR_TREND}+ "
                f"qo'ng'iroq kerak (joriy: {current_n}, oldingi: {previous_n})"
            )
        return ConversionTrend(
            days=days,
            current_rate=rate(current),
            previous_rate=rate(previous),
            current_calls=current_n,
            previous_calls=previous_n,
            reliable=reliable,
            reason=reason,
        )

    async def conversion_trend(self, days: int = 30) -> ConversionTrend:
        current = await self.fetch_scored_calls(days)
        previous = await self.fetch_scored_calls(days, offset_days=days)
        return self.build_trend(current, previous, days)

    @staticmethod
    def true_efficiency(converted_calls: int, all_calls_including_missed: int) -> float:
        if all_calls_including_missed <= 0:
            return 0.0
        return converted_calls / all_calls_including_missed * 100

    async def team_summary(self, days: int = 30) -> Dict[str, Any]:
        rows = await self.fetch_scored_calls(days)
        previous = await self.fetch_scored_calls(days, offset_days=days)
        trend = self.build_trend(rows, previous, days)
        diagnoses = self.diagnose_rows(rows)
        scored = [r for r in rows if int(_row_get(r, "overall_score", 0) or 0) > 0]
        converted = [r for r in scored if _is_converted(r)]
        revenue = aggregate_revenue(scored)
        events = await CallEventLog(self.db).fetch_recent(days)
        volume = team_volume(events)
        by_manager_volume = aggregate_volume(events)

        stage_focus: Dict[str, int] = defaultdict(int)
        for item in diagnoses:
            if item.growth_stage:
                stage_focus[item.growth_stage] += 1

        return {
            "days": days,
            "total_calls": len(scored),
            "converted_calls": len(converted),
            "conversion_rate": round(
                (len(converted) / len(scored) * 100) if scored else 0.0, 1
            ),
            "avg_score": round(
                _mean([float(_row_get(r, "overall_score", 0) or 0) for r in scored]), 1
            ),
            "trend": trend.to_dict(),
            "volume": {
                "total": volume.total,
                "answered": volume.answered,
                "missed": volume.missed,
                "answer_rate": round(volume.answer_rate, 1),
                "avg_duration": volume.avg_duration_label,
            },
            "true_efficiency": round(
                self.true_efficiency(len(converted), volume.total or len(scored)), 1
            ),
            "seller_volume": [v.to_dict() for v in by_manager_volume.values()],
            "revenue_won": round(sum(r.revenue_won for r in revenue.values())),
            "revenue_at_risk": round(sum(r.revenue_lost for r in revenue.values())),
            "revenue_open": round(sum(r.revenue_open for r in revenue.values())),
            "sellers": [d.to_dict() for d in diagnoses],
            "team_focus": [
                {
                    "stage": stage,
                    "label": STAGE_LABELS_UZ.get(stage, stage),
                    "sellers_affected": count,
                    "drill": STAGE_DRILLS_UZ.get(stage, ""),
                }
                for stage, count in sorted(stage_focus.items(), key=lambda kv: -kv[1])
            ],
            "has_data": bool(scored),
        }

    build_seller_card = staticmethod(build_seller_card)

    def build_team_report(
        self,
        diagnoses: Sequence[SellerDiagnosis],
        trend: Optional[ConversionTrend] = None,
        volumes: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        return build_team_report(diagnoses, trend, volumes)

    async def generate_seller_cards(self, days: int = 30) -> List[tuple[str, str]]:
        diagnoses = await self.diagnose_all(days)
        volumes = await self.fetch_volumes(days)
        return [
            (d.manager_name, self.build_seller_card(d, volumes.get(d.manager_name)))
            for d in diagnoses
        ]

    async def fetch_volumes(self, days: int = 30) -> Dict[str, Any]:
        events = await CallEventLog(self.db).fetch_recent(days)
        volumes: Dict[str, Any] = dict(aggregate_volume(events))
        volumes["__team__"] = team_volume(events)
        return volumes

    async def generate_team_report(self, days: int = 30) -> Optional[str]:
        diagnoses = await self.diagnose_all(days)
        trend = await self.conversion_trend(days)
        volumes = await self.fetch_volumes(days)
        return self.build_team_report(diagnoses, trend, volumes)
