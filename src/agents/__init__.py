"""
Oisha-OS Agents Package

Ideal AI Agent darajasidagi komponentlar:
- SurgicalNegotiator: Asosiy avtonom negotiator
- AutonomousSalesAgent: Self-directed savdo agenti
- DealLifecycleManager: Pipeline boshqaruvchi
- NegotiationEngine: Savdo tahlil tizimi
- ContractGenerator: Avtomatik shartnomalar
- RiskAssessor: Xavf baholash
"""

from src.agents.surgical_negotiator import (
    SurgicalNegotiator,
    get_surgical_negotiator,
    negotiate,
)

from src.agents.autonomous_sales_agent import (
    AutonomousSalesAgent,
    ConversationState,
    DealProposal,
    PricingEngine,
    get_autonomous_agent,
)

from src.agents.deal_lifecycle_manager import (
    DealLifecycleManager,
    DealStage,
    DealPriority,
    Deal,
    get_lifecycle_manager,
)

from src.agents.negotiation_engine import (
    NegotiationEngine,
    NegotiationAssessment,
)

from src.agents.contract_generator import (
    ContractGenerator,
    RiskAssessor,
    ContractTemplate,
)

__all__ = [
    # Main orchestrator
    "SurgicalNegotiator",
    "get_surgical_negotiator",
    "negotiate",
    # Sales agent
    "AutonomousSalesAgent",
    "ConversationState",
    "DealProposal",
    "PricingEngine",
    "get_autonomous_agent",
    # Lifecycle
    "DealLifecycleManager",
    "DealStage",
    "DealPriority",
    "Deal",
    "get_lifecycle_manager",
    # Negotiation
    "NegotiationEngine",
    "NegotiationAssessment",
    # Contract
    "ContractGenerator",
    "RiskAssessor",
    "ContractTemplate",
]
