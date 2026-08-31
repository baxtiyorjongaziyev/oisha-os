"""
Facade for Deal Lifecycle Manager.
Delegates to modular subpackage in src.agents.pipeline.
"""
from src.agents.pipeline.models import DealStage, DealPriority, Deal
from src.agents.pipeline.automations import LifecycleAutomationsMixin
from src.agents.pipeline.manager import (
    DealLifecycleManager,
    get_lifecycle_manager,
)

__all__ = [
    "DealStage",
    "DealPriority",
    "Deal",
    "LifecycleAutomationsMixin",
    "DealLifecycleManager",
    "get_lifecycle_manager",
]
