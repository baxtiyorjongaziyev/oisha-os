"""
Agency Personas package aggregating all domain persona definitions.
"""
from typing import Dict
from src.services.personas.sales import SALES_PERSONAS
from src.services.personas.marketing import MARKETING_PERSONAS
from src.services.personas.operations import OPERATIONS_PERSONAS
from src.services.personas.creative import CREATIVE_PERSONAS

AGENCY_PERSONAS: Dict[str, str] = {}
AGENCY_PERSONAS.update(SALES_PERSONAS)
AGENCY_PERSONAS.update(MARKETING_PERSONAS)
AGENCY_PERSONAS.update(OPERATIONS_PERSONAS)
AGENCY_PERSONAS.update(CREATIVE_PERSONAS)

__all__ = [
    "AGENCY_PERSONAS",
    "SALES_PERSONAS",
    "MARKETING_PERSONAS",
    "OPERATIONS_PERSONAS",
    "CREATIVE_PERSONAS",
]
