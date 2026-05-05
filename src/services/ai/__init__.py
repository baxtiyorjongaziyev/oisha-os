"""AI-powered quality control and analytics for AmoCRM."""

from .quality_analyzer import QualityAnalyzer, ConversationAnalysis
from .call_analytics import CallAnalytics
from .task_manager import AITaskManager
from .conversation_engine import ConversationEngine, CallRecord, get_conversation_engine

__all__ = [
    "QualityAnalyzer",
    "ConversationAnalysis",
    "CallAnalytics",
    "AITaskManager",
    "ConversationEngine",
    "CallRecord",
    "get_conversation_engine",
]
