"""
Systematizer package for Oisha-OS.
Autonomous repetitive action identification, pattern detection, and systematization engine.
"""
from src.services.core.systematizer.models import (
    AutomationStrategy,
    DetectedPattern,
    PatternType,
    ProposalStatus,
    SystematizationProposal,
    SystematizationReport,
)
from src.services.core.systematizer.detector import PatternDetector

__all__ = [
    "AutomationStrategy",
    "DetectedPattern",
    "PatternDetector",
    "PatternType",
    "ProposalStatus",
    "SystematizationProposal",
    "SystematizationReport",
]
