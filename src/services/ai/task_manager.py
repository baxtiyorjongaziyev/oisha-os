"""
Facade for AI Task Manager.
Delegates to modular subpackage in src.services.ai.task_creation.
"""
from src.services.ai.task_creation.builders import (
    TASK_TYPES,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_LOW,
    detect_task_type,
    estimate_due_hours,
    create_quality_tasks,
    create_objection_tasks,
    create_followup_tasks,
    create_mood_based_tasks,
)
from src.services.ai.task_creation.reporting import (
    get_task_summary,
    generate_task_report,
)
from src.services.ai.task_creation.manager import AITaskManager

__all__ = [
    "TASK_TYPES",
    "PRIORITY_HIGH",
    "PRIORITY_MEDIUM",
    "PRIORITY_LOW",
    "AITaskManager",
    "detect_task_type",
    "estimate_due_hours",
    "create_quality_tasks",
    "create_objection_tasks",
    "create_followup_tasks",
    "create_mood_based_tasks",
    "get_task_summary",
    "generate_task_report",
]
