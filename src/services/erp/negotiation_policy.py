from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class NegotiationPolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False


class NegotiationPolicy:
    def __init__(
        self,
        *,
        max_unanswered_follow_ups: int = 3,
        minimum_follow_up_interval: timedelta = timedelta(hours=24),
    ) -> None:
        self.max_unanswered_follow_ups = max(0, int(max_unanswered_follow_ups))
        self.minimum_follow_up_interval = minimum_follow_up_interval

    def evaluate_proposal(
        self,
        *,
        stage: str,
        service: str,
        amount: float,
        approved_prices: dict[str, dict[str, Any]],
    ) -> NegotiationPolicyDecision:
        proposal_stages = {
            "QUALIFIED",
            "EXPERT_MEETING",
            "PROPOSAL",
            "FOLLOW_UP",
            "NEGOTIATION",
        }
        if str(stage).upper() not in proposal_stages:
            return NegotiationPolicyDecision(False, "proposal_requires_qualified_stage")
        bounds = dict(approved_prices.get(str(service)) or {})
        if not bounds:
            return NegotiationPolicyDecision(False, "service_price_not_approved")
        minimum = float(bounds.get("min") or 0)
        maximum = float(bounds.get("max") or 0)
        if float(amount) < minimum or not maximum or float(amount) > maximum:
            return NegotiationPolicyDecision(False, "price_outside_approved_range")
        return NegotiationPolicyDecision(True, "approved_price")

    def evaluate_discount(
        self,
        *,
        discount_percent: float,
        owner_approved: bool = False,
    ) -> NegotiationPolicyDecision:
        if float(discount_percent) <= 0:
            return NegotiationPolicyDecision(True, "no_discount")
        if not owner_approved:
            return NegotiationPolicyDecision(
                False,
                "discount_requires_owner_approval",
                requires_approval=True,
            )
        return NegotiationPolicyDecision(
            True,
            "owner_approved_discount",
            requires_approval=True,
        )

    def evaluate_follow_up(
        self,
        *,
        unanswered_count: int,
        last_contacted_at: datetime | None = None,
        now: datetime | None = None,
    ) -> NegotiationPolicyDecision:
        if int(unanswered_count) >= self.max_unanswered_follow_ups:
            return NegotiationPolicyDecision(False, "follow_up_limit_reached")
        if last_contacted_at is not None and now is not None:
            if now - last_contacted_at < self.minimum_follow_up_interval:
                return NegotiationPolicyDecision(False, "follow_up_too_soon")
        return NegotiationPolicyDecision(True, "follow_up_allowed")
