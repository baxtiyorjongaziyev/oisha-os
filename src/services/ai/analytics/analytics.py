"""
CallAnalytics service implementation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.ai.analytics.aggregations import CallAnalyticsAggregationsMixin
from src.services.ai.quality_analyzer import ConversationAnalysis

logger = logging.getLogger(__name__)


class CallAnalytics(CallAnalyticsAggregationsMixin):
    """Qo'ng'iroqlar tahlili va vizualizatsiya ma'lumotlari."""

    def __init__(self):
        self.analyses: List[ConversationAnalysis] = []

    def add_analysis(self, analysis: ConversationAnalysis):
        self.analyses.append(analysis)

    def add_analyses(self, analyses: List[ConversationAnalysis]):
        self.analyses.extend(analyses)

    def get_dashboard_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        manager_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        filtered = self.analyses
        if manager_name:
            filtered = [a for a in filtered if a.manager_name == manager_name]
        filtered = self._filter_by_date(filtered, start_date, end_date)

        if not filtered:
            return self._get_empty_dashboard()

        return {
            "summary": self._get_summary_stats(filtered),
            "daily_stats": self._get_daily_stats(filtered),
            "manager_ratings": self._get_manager_ratings(filtered),
            "quality_distribution": self._get_quality_distribution(filtered),
            "outcome_analysis": self._get_outcome_analysis(filtered),
            "objection_analysis": self._get_objection_analysis(filtered),
            "lost_clients": self._analyze_lost_clients(filtered),
            "time_analysis": self._get_time_analysis(filtered),
            "recommendations": self._generate_recommendations(filtered),
        }

    def get_manager_dashboard(
        self,
        manager_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        manager_analyses = [a for a in self.analyses if a.manager_name == manager_name]
        manager_analyses = self._filter_by_date(manager_analyses, start_date, end_date)

        if not manager_analyses:
            return {"error": f"'{manager_name}' uchun ma'lumot topilmadi"}

        return {
            "manager_name": manager_name,
            "summary": self._get_summary_stats(manager_analyses),
            "daily_stats": self._get_daily_stats(manager_analyses),
            "skill_breakdown": self._get_skill_breakdown(manager_analyses),
            "top_strengths": self._get_top_strengths(manager_analyses),
            "improvement_areas": self._get_improvement_areas(manager_analyses),
            "trend": self._calculate_trend(manager_analyses),
            "progress_over_time": self._get_progress_over_time(manager_analyses),
        }
