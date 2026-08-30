"""
Facade for Pipeline Auditor.
Delegates to modular subpackage in src.services.core.pipeline.
"""
from src.services.core.pipeline.helpers import _maybe_await, _save_user_intelligence
from src.services.core.pipeline.ai_profile import generate_intelligence_profile
from src.services.core.pipeline.auditor import PipelineAuditor

__all__ = [
    "PipelineAuditor",
    "_maybe_await",
    "_save_user_intelligence",
    "generate_intelligence_profile",
]
