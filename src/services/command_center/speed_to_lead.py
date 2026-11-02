"""Speed to Lead (SLA) response time calculator and analytics module.

Computes response time buckets, SLA compliance rates, and longest waiting customer
alerts across channels (Telegram, Instagram, Phone) for the Executive Dashboard.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class LeadInteraction:
    """Represents a lead contact event and its initial response timestamp."""

    lead_id: str
    customer_name: str
    channel: str
    manager_id: str
    created_at: datetime
    first_response_at: Optional[datetime] = None


@dataclass
class WaitingCustomer:
    """Detailed information about the longest waiting customer."""

    lead_id: str
    customer_name: str
    channel: str
    manager_id: str
    wait_minutes: float


@dataclass
class SpeedToLeadMetrics:
    """Aggregated speed-to-lead and SLA compliance metrics."""

    total_leads: int = 0
    answered_leads: int = 0
    unanswered_leads: int = 0
    sla_rate_pct: float = 0.0
    avg_response_minutes: float = 0.0
    buckets: Dict[str, int] = field(
        default_factory=lambda: {
            "within_15m": 0,
            "within_30m": 0,
            "within_1h": 0,
            "within_2h": 0,
            "over_2h": 0,
            "unanswered": 0,
        }
    )
    channel_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)
    longest_wait: Optional[WaitingCustomer] = None


class SpeedToLeadCalculator:
    """Calculates response time distributions and SLA compliance metrics."""

    def __init__(
        self,
        reference_time: Optional[datetime] = None,
        target_sla_minutes: float = 30.0,
    ) -> None:
        """Initialize calculator with target SLA and optional fixed reference time."""
        self.reference_time = reference_time or datetime.now(timezone.utc)
        self.target_sla_minutes = target_sla_minutes

    def calculate(self, interactions: List[LeadInteraction]) -> SpeedToLeadMetrics:
        """Compute complete speed-to-lead metrics from a list of interactions."""
        if not interactions:
            return SpeedToLeadMetrics()

        buckets = {
            "within_15m": 0,
            "within_30m": 0,
            "within_1h": 0,
            "within_2h": 0,
            "over_2h": 0,
            "unanswered": 0,
        }
        channel_durations: Dict[str, List[float]] = {}
        total_duration = 0.0
        answered_count = 0
        sla_compliant_count = 0
        longest_wait_obj: Optional[WaitingCustomer] = None
        max_wait_minutes = -1.0

        for item in interactions:
            wait_min = self._calculate_wait_minutes(item)
            longest_wait_obj, max_wait_minutes = self._update_longest_wait(
                item, wait_min, longest_wait_obj, max_wait_minutes
            )

            if item.first_response_at is None:
                buckets["unanswered"] += 1
                continue

            resp_min = (item.first_response_at - item.created_at).total_seconds() / 60.0
            resp_min = max(0.0, resp_min)
            answered_count += 1
            total_duration += resp_min

            if resp_min <= self.target_sla_minutes:
                sla_compliant_count += 1

            self._assign_bucket(resp_min, buckets)
            self._record_channel_duration(item.channel, resp_min, channel_durations)

        avg_resp = (total_duration / answered_count) if answered_count > 0 else 0.0
        sla_rate = (sla_compliant_count / len(interactions)) * 100.0 if interactions else 0.0
        channel_stats = self._build_channel_stats(channel_durations)

        return SpeedToLeadMetrics(
            total_leads=len(interactions),
            answered_leads=answered_count,
            unanswered_leads=len(interactions) - answered_count,
            sla_rate_pct=round(sla_rate, 1),
            avg_response_minutes=round(avg_resp, 1),
            buckets=buckets,
            channel_breakdown=channel_stats,
            longest_wait=longest_wait_obj,
        )

    def _calculate_wait_minutes(self, item: LeadInteraction) -> float:
        """Calculate wait duration in minutes relative to response or reference time."""
        end_time = item.first_response_at or self.reference_time
        duration_seconds = (end_time - item.created_at).total_seconds()
        return max(0.0, duration_seconds / 60.0)

    def _update_longest_wait(
        self,
        item: LeadInteraction,
        wait_min: float,
        current_longest: Optional[WaitingCustomer],
        max_minutes: float,
    ) -> tuple[Optional[WaitingCustomer], float]:
        """Update and return the customer with the longest wait duration."""
        if wait_min > max_minutes:
            new_customer = WaitingCustomer(
                lead_id=item.lead_id,
                customer_name=item.customer_name,
                channel=item.channel,
                manager_id=item.manager_id,
                wait_minutes=round(wait_min, 1),
            )
            return new_customer, wait_min
        return current_longest, max_minutes

    def _assign_bucket(self, minutes: float, buckets: Dict[str, int]) -> None:
        """Increment the appropriate time bucket for an answered lead."""
        if minutes <= 15.0:
            buckets["within_15m"] += 1
        elif minutes <= 30.0:
            buckets["within_30m"] += 1
        elif minutes <= 60.0:
            buckets["within_1h"] += 1
        elif minutes <= 120.0:
            buckets["within_2h"] += 1
        else:
            buckets["over_2h"] += 1

    def _record_channel_duration(
        self,
        channel: str,
        duration: float,
        channel_durations: Dict[str, List[float]],
    ) -> None:
        """Append duration to channel-specific aggregation list."""
        if channel not in channel_durations:
            channel_durations[channel] = []
        channel_durations[channel].append(duration)

    def _build_channel_stats(
        self, channel_durations: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """Compute counts and averages per communication channel."""
        stats: Dict[str, Dict[str, float]] = {}
        for chan, durations in channel_durations.items():
            avg_val = sum(durations) / len(durations) if durations else 0.0
            stats[chan] = {
                "count": float(len(durations)),
                "avg_minutes": round(avg_val, 1),
            }
        return stats
