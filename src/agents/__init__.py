"""
Oisha-OS Agents Package

## Arxitektura: ikkita parallel yo'l

### 1. Surgical path (asosiy, SURGICAL_MODE=True by default)
   surgical_integration.py → SurgicalNegotiator → AutonomousSalesAgent
   Trigger: savdo kalit so'zlari (narx, loyiha, shartnoma...)
   Entry: main.py `should_use_surgical()` check

### 2. Standard path (fallback / oddiy xabarlar)
   message_controller.py → SalesAgent + NegotiationEngine
   SalesAgent: Telegram suhbat handler (eskalatsiya, reengagement)
   NegotiationEngine: Semantic assessment (Gemini, holat tahlili)

### 3. Web API path
   api_server.py → AutonomousSalesAgent (to'g'ridan-to'g'ri)

### Yordamchi komponentlar (SalesAgent tomonidan ishlatiladi)
   negotiation_reengagement.py — reengagement kandidatlarini tanlash
   negotiation_verifier.py — bitim yopilish holati
   persona_router.py — persona yo'naltirish

### Tahlil: agents/ da dead code yo'q (2026-06-22)
   ai_router.py — faqat testlarda ishlatiladi (ishlab chiqarish kodi chaqirmaydi)
   Barcha boshqa agentlar aktiv importlangan.
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

from src.agents.web_driver import OishaWebDriver
from src.agents.os_driver import OishaOSDriver
from src.agents.mobile_proxy import OishaMobileProxy, OishaTelegramProxy

__all__ = [
    # Surgical path — SurgicalNegotiator → AutonomousSalesAgent
    "SurgicalNegotiator",
    "get_surgical_negotiator",
    "negotiate",
    "AutonomousSalesAgent",
    "ConversationState",
    "DealProposal",
    "PricingEngine",
    "get_autonomous_agent",
    # Standard path — SalesAgent + NegotiationEngine (message_controller.py)
    "NegotiationEngine",
    "NegotiationAssessment",
    # Lifecycle & contracts
    "DealLifecycleManager",
    "DealStage",
    "DealPriority",
    "Deal",
    "get_lifecycle_manager",
    "ContractGenerator",
    "RiskAssessor",
    "ContractTemplate",
    # Drivers / Proxies
    "OishaWebDriver",
    "OishaOSDriver",
    "OishaMobileProxy",
    "OishaTelegramProxy",
]
