"""
Facade for Call Analytics.
Delegates to modular subpackage in src.services.ai.analytics.
"""
from src.services.ai.analytics.models import (
    DailyStats,
    ManagerPerformance,
    LostClientAnalysis,
)
from src.services.ai.analytics.aggregations import CallAnalyticsAggregationsMixin
from src.services.ai.analytics.analytics import CallAnalytics

__all__ = [
    "DailyStats",
    "ManagerPerformance",
    "LostClientAnalysis",
    "CallAnalyticsAggregationsMixin",
    "CallAnalytics",
]
