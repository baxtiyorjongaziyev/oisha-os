"""
Conversation analysis engine package.
"""
from src.services.ai.conversation.models import CallRecord, DashboardMetrics
from src.services.ai.conversation.reporting import ConversationReportingMixin
from src.services.ai.conversation.engine import ConversationEngine

_engine_instance = None

def get_conversation_engine() -> ConversationEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ConversationEngine()
    return _engine_instance

__all__ = [
    "CallRecord",
    "DashboardMetrics",
    "ConversationReportingMixin",
    "ConversationEngine",
    "get_conversation_engine",
]
