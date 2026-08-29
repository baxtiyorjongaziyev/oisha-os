"""
Facade for Smart Task Creator.
Delegates to modular subpackage in src.services.core.smart_tasks.
"""
from src.services.core.smart_tasks import (
    SmartTaskCreator,
    get_smart_task_creator,
    run_smart_task_creation,
)

__all__ = [
    "SmartTaskCreator",
    "get_smart_task_creator",
    "run_smart_task_creation",
]
