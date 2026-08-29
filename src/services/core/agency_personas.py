"""
Facade for Agency Personas.
Delegates to modular subpackage in src.services.personas.
"""
from src.services.personas import (
    AGENCY_PERSONAS,
    CREATIVE_PERSONAS,
    MARKETING_PERSONAS,
    OPERATIONS_PERSONAS,
    SALES_PERSONAS,
)

__all__ = [
    "AGENCY_PERSONAS",
    "SALES_PERSONAS",
    "MARKETING_PERSONAS",
    "OPERATIONS_PERSONAS",
    "CREATIVE_PERSONAS",
]
