"""
Facade for Negotiation Engine.
Delegates to modular subpackage in src.agents.negotiation.
"""
from google import genai
from src.agents.negotiation.models import NegotiationAssessment
from src.agents.negotiation.rule_assessor import NegotiationRuleMixin
from src.agents.negotiation.engine import (
    NegotiationEngine,
    transcribe_and_assess_audio,
)

__all__ = [
    "genai",
    "NegotiationAssessment",
    "NegotiationRuleMixin",
    "NegotiationEngine",
    "transcribe_and_assess_audio",
]
