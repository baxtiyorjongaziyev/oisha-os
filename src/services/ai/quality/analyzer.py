"""
QualityAnalyzer main service composing AI, heuristic scoring, and feedback mixins.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.services.core.sales_playbook import metric_weights
from src.services.ai.quality.models import (
    QualityMetric,
)
from src.services.ai.quality.ai_engine import AIEngineMixin
from src.services.ai.quality.scoring_heuristics import ScoringHeuristicsMixin
from src.services.ai.quality.feedback_generator import FeedbackGeneratorMixin

logger = logging.getLogger("QualityAnalyzer")


class QualityAnalyzer(AIEngineMixin, ScoringHeuristicsMixin, FeedbackGeneratorMixin):
    """
    AI-powered conversation quality analyzer.
    """

    DEFAULT_WEIGHTS = {
        QualityMetric(metric): weight for metric, weight in metric_weights().items()
    }

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        gemini_client: Optional[Any] = None,
    ):
        self.api_key = openai_api_key
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self._gemini_client = gemini_client

    def set_weights(self, weights: Dict[QualityMetric, float]):
        """Og'irliklarni sozlash."""
        self.weights.update(weights)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
