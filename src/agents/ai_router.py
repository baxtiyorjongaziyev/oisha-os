"""
Facade for AI Router.
Delegates to modular subpackage in src.agents.router_pkg.
"""
from src.agents.router_pkg.models_cost import (
    TASK_TO_TIER,
    MODEL_TIERS,
    TIER_COST_PER_1K,
    DAILY_COST_LIMIT_USD,
    TaskType,
    _cache,
    get_daily_summary,
)
from src.agents.router_pkg.router import route

__all__ = [
    "TASK_TO_TIER",
    "MODEL_TIERS",
    "TIER_COST_PER_1K",
    "DAILY_COST_LIMIT_USD",
    "TaskType",
    "_cache",
    "get_daily_summary",
    "route",
]
