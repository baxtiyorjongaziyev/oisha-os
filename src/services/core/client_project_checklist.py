"""
Facade for Client Project Checklist.
Delegates to modular subpackage in src.services.core.project_checklist.
"""
from src.services.core.project_checklist import (
    ClientProject,
    ClientProjectChecklistManager,
    complete_project_phase,
    create_branding_project,
    get_client_project_manager,
    get_project_status,
)

__all__ = [
    "ClientProject",
    "ClientProjectChecklistManager",
    "complete_project_phase",
    "create_branding_project",
    "get_client_project_manager",
    "get_project_status",
]
