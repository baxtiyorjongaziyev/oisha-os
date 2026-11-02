"""Stuck Deals (Qolib ketgan bitimlar) Radar Service.

Identifies deals idling in pipeline stages beyond healthy thresholds,
calculates stalled capital, and highlights the oldest unprogressed deals.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class DealStageRecord:
    """Record of a deal and its current stage timing in CRM."""

    deal_id: str
    deal_name: str
    stage_id: str
    stage_name: str
    manager_id: str
    manager_name: str
    amount: float
    entered_stage_at: datetime


@dataclass
class StuckDealDetail:
    """Detailed record for a specific stalled deal."""

    deal_id: str
    deal_name: str
    stage_id: str
    stage_name: str
    manager_id: str
    manager_name: str
    amount: float
    stuck_days: int


@dataclass
class StageStuckSummary:
    """Stuck deal metrics aggregated by pipeline stage."""

    stage_id: str
    stage_name: str
    stuck_count: int
    oldest_days: int
    stuck_amount: float


@dataclass
class StuckDealsSummary:
    """Overall dashboard summary of all stalled deals across pipelines."""

    total_stuck_deals: int = 0
    total_stuck_value: float = 0.0
    stage_summaries: List[StageStuckSummary] = field(default_factory=list)
    oldest_deal: Optional[StuckDealDetail] = None
    stuck_deals_list: List[StuckDealDetail] = field(default_factory=list)


class StuckDealsRadar:
    """Analyzes pipeline duration and flags deals exceeding threshold days."""

    DEFAULT_THRESHOLD_DAYS: int = 3

    def __init__(
        self,
        reference_time: Optional[datetime] = None,
        stage_thresholds_days: Optional[Dict[str, int]] = None,
        default_threshold_days: int = 3,
    ) -> None:
        """Initialize radar with optional custom thresholds and reference time."""
        self.reference_time = reference_time or datetime.now(timezone.utc)
        self.stage_thresholds_days = stage_thresholds_days or {}
        self.default_threshold_days = default_threshold_days

    def analyze(self, deals: List[DealStageRecord]) -> StuckDealsSummary:
        """Analyze a list of active deals and compute stuck deal analytics."""
        if not deals:
            return StuckDealsSummary()

        stuck_deals: List[StuckDealDetail] = []
        oldest_deal: Optional[StuckDealDetail] = None
        max_days = -1

        for deal in deals:
            threshold = self._get_threshold_for_stage(deal.stage_id)
            days_in_stage = self._calculate_days_in_stage(deal.entered_stage_at)

            if days_in_stage >= threshold:
                detail = StuckDealDetail(
                    deal_id=deal.deal_id,
                    deal_name=deal.deal_name,
                    stage_id=deal.stage_id,
                    stage_name=deal.stage_name,
                    manager_id=deal.manager_id,
                    manager_name=deal.manager_name,
                    amount=deal.amount,
                    stuck_days=days_in_stage,
                )
                stuck_deals.append(detail)
                if days_in_stage > max_days:
                    max_days = days_in_stage
                    oldest_deal = detail

        stage_summaries = self._aggregate_by_stage(stuck_deals)
        total_value = sum(d.amount for d in stuck_deals)

        return StuckDealsSummary(
            total_stuck_deals=len(stuck_deals),
            total_stuck_value=round(total_value, 2),
            stage_summaries=stage_summaries,
            oldest_deal=oldest_deal,
            stuck_deals_list=stuck_deals,
        )

    def _get_threshold_for_stage(self, stage_id: str) -> int:
        """Return the threshold in days for the given stage id."""
        return self.stage_thresholds_days.get(stage_id, self.default_threshold_days)

    def _calculate_days_in_stage(self, entered_at: datetime) -> int:
        """Calculate elapsed full days from entering stage to reference time."""
        delta = self.reference_time - entered_at
        return max(0, int(delta.total_seconds() // 86400))

    def _aggregate_by_stage(
        self, stuck_deals: List[StuckDealDetail]
    ) -> List[StageStuckSummary]:
        """Aggregate stalled deals by their pipeline stage."""
        stage_map: Dict[str, Dict[str, object]] = {}

        for deal in stuck_deals:
            s_id = deal.stage_id
            if s_id not in stage_map:
                stage_map[s_id] = {
                    "stage_name": deal.stage_name,
                    "count": 0,
                    "oldest": 0,
                    "amount": 0.0,
                }
            stage_map[s_id]["count"] = int(stage_map[s_id]["count"]) + 1
            stage_map[s_id]["amount"] = float(stage_map[s_id]["amount"]) + deal.amount
            if deal.stuck_days > int(stage_map[s_id]["oldest"]):
                stage_map[s_id]["oldest"] = deal.stuck_days

        summaries = [
            StageStuckSummary(
                stage_id=s_id,
                stage_name=str(data["stage_name"]),
                stuck_count=int(data["count"]),
                oldest_days=int(data["oldest"]),
                stuck_amount=round(float(data["amount"]), 2),
            )
            for s_id, data in stage_map.items()
        ]
        summaries.sort(key=lambda s: s.stuck_count, reverse=True)
        return summaries

    def build_warning_message(self, summary: StuckDealsSummary) -> str:
        """Format an operational alert string for managers and team leaders."""
        if summary.total_stuck_deals == 0:
            return "Hozircha qolib ketgan bitimlar yoʻq. Barcha bosqichlar meʼyorda."

        lines = [
            f"Diqqat: {summary.total_stuck_deals} ta bitim bosqichidan siljimagan.",
            f"Jami toʻxtab qolgan summa: {summary.total_stuck_value:,.0f} soʻm.",
        ]
        if summary.oldest_deal:
            oldest = summary.oldest_deal
            lines.append(
                f"Eng eskisi: «{oldest.deal_name}» ({oldest.stuck_days} kun, masʼul: {oldest.manager_name})."
            )
        return "\n".join(lines)
