"""
Facade for AmoCRM Deal AI Analyzer.
Delegates to modular subpackage in src.services.core.deal_ai.
"""
from src.services.core.deal_ai.models import (
    PHONE_RE,
    USERNAME_RE,
    CATEGORY_TAGS,
    CATEGORY_LABEL_UZ,
    ANALYZER_PROMPT,
    DealAnalysis,
    AnalyzerReport,
    report_to_dict,
)
from src.services.core.deal_ai.analyzer import DealAIAnalyzer

__all__ = [
    "PHONE_RE",
    "USERNAME_RE",
    "CATEGORY_TAGS",
    "CATEGORY_LABEL_UZ",
    "ANALYZER_PROMPT",
    "DealAnalysis",
    "AnalyzerReport",
    "report_to_dict",
    "DealAIAnalyzer",
]
