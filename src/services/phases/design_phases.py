"""
Design and creative sub-phase generator delegating to specialized phase modules.
"""
from typing import List
from src.services.phases.models import ProjectPhase
from src.services.phases.design_subphases_branding import add_branding_phases
from src.services.phases.design_subphases_media import add_media_phases


def build_design_phases(services: List[str]) -> List[ProjectPhase]:
    """Dynamically construct design sub-phases based on services list."""
    phases: List[ProjectPhase] = []
    service_str = " ".join(services).lower()
    add_branding_phases(services, phases, service_str)
    add_media_phases(services, phases, service_str)
    return phases
