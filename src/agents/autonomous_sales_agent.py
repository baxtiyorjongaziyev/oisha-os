"""
Facade for Autonomous Sales Agent.
Delegates to modular subpackage in src.agents.closer.
"""
from src.agents.closer.models import ConversationState, DealProposal
from src.agents.closer.proposals import PricingEngine, ProposalEngine
from src.agents.closer.decisions import AutonomousDecisionsMixin
from src.agents.closer.agent import (
    AutonomousSalesAgent,
    get_autonomous_agent,
)

__all__ = [
    "ConversationState",
    "DealProposal",
    "PricingEngine",
    "ProposalEngine",
    "AutonomousDecisionsMixin",
    "AutonomousSalesAgent",
    "get_autonomous_agent",
]
