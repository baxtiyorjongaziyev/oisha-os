"""
Facade for Oisha Self Diagnosis.
Delegates to modular subpackage in src.services.core.diagnosis.
"""
from src.services.core.diagnosis import (
    CATEGORY_CODE,
    CATEGORY_ERROR,
    CATEGORY_FEATURE,
    CATEGORY_HEALTH,
    CATEGORY_PERF,
    SEVERITY_CRITICAL,
    SEVERITY_EMOJI,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ImprovementProposal,
    OishaSelfDiagnosis,
)

__all__ = [
    "CATEGORY_CODE",
    "CATEGORY_ERROR",
    "CATEGORY_FEATURE",
    "CATEGORY_HEALTH",
    "CATEGORY_PERF",
    "SEVERITY_CRITICAL",
    "SEVERITY_EMOJI",
    "SEVERITY_HIGH",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "ImprovementProposal",
    "OishaSelfDiagnosis",
]

