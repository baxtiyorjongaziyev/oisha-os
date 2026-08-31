"""
ai_router — Markazlashgan LLM router (Gemini-first stack).
Facade for src.agents.router_pkg.
"""
import asyncio
from src.settings import settings
from src.agents.router_pkg.models_cost import (
    MODEL_CATALOG,
    TASK_TO_TIER,
    TaskType,
    _cache,
    _cache_get,
    _cache_put,
    _error_result,
    _estimate_cost,
    _log_usage,
    _maybe_degrade_tier,
    get_daily_summary,
)
from src.agents.router_pkg.router import (
    _call_gemini,
    _get_gemini_client,
    route,
)

__all__ = [
    "TaskType",
    "TASK_TO_TIER",
    "MODEL_CATALOG",
    "route",
    "get_daily_summary",
    "_cache",
    "_get_gemini_client",
    "_maybe_degrade_tier",
    "_call_gemini",
    "_estimate_cost",
    "_log_usage",
    "_error_result",
    "_cache_get",
    "_cache_put",
    "asyncio",
    "settings",
]
