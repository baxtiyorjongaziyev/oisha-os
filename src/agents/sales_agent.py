"""
Facade for Sales Agent.
Delegates to modular subpackage in src.agents.sales_pkg.
"""
from src.agents.negotiation_engine import NegotiationEngine
from src.agents.sales_pkg.helpers import (
    ESCALATION_TRIGGERS,
    ESCALATION_CLOSE_PROB_THRESHOLD,
    ESCALATION_RISK_FLAGS,
    SalesFormattingMixin,
)
from src.agents.sales_pkg.actions import SalesActionsMixin
from src.agents.sales_pkg.agent import SalesAgent

__all__ = [
    "NegotiationEngine",
    "ESCALATION_TRIGGERS",
    "ESCALATION_CLOSE_PROB_THRESHOLD",
    "ESCALATION_RISK_FLAGS",
    "SalesFormattingMixin",
    "SalesActionsMixin",
    "SalesAgent",
]
