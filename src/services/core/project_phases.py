"""
Facade for Project Phases Management.
Delegates to modular subpackage in src.services.phases.
"""
from src.services.phases import (
    PhaseRole,
    PhaseStatus,
    ProjectChecklist,
    ProjectPhase,
    ProjectPhaseManager,
    build_design_phases,
    build_phase_templates,
    get_project_phase_manager,
)

__all__ = [
    "PhaseStatus",
    "PhaseRole",
    "ProjectPhase",
    "ProjectChecklist",
    "build_phase_templates",
    "build_design_phases",
    "ProjectPhaseManager",
    "get_project_phase_manager",
]
