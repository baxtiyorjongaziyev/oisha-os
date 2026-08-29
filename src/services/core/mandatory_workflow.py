"""
Facade for Mandatory Workflow.
Delegates to modular subpackage in src.services.core.workflow_engine.
"""
from src.services.core.workflow_engine import (
    MandatoryWorkflowManager,
    Role,
    TaskStatus,
    UserTask,
    WorkflowStep,
    get_mandatory_workflow,
)

__all__ = [
    "MandatoryWorkflowManager",
    "Role",
    "TaskStatus",
    "UserTask",
    "WorkflowStep",
    "get_mandatory_workflow",
]
