"""
ClientProjectChecklistManager main class and convenience helper functions.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.context import app_ctx
from src.services.core.project_checklist.models import ClientProject, ServiceType
from src.services.core.project_checklist.phases_ops import PhaseOperationsMixin
from src.services.core.project_checklist.reporting_ops import ReportingOperationsMixin
from src.services.core.project_checklist.service_config import get_service_configurator
from src.services.core.project_phases import get_project_phase_manager
from src.services.core.workflow_engine import get_mandatory_workflow

logger = logging.getLogger("ClientProjectChecklist")


class ClientProjectChecklistManager(PhaseOperationsMixin, ReportingOperationsMixin):
    """
    Mijoz loyihalari uchun checklistlar boshqaruvchisi.
    """

    def __init__(self):
        self.service_config = get_service_configurator()
        self.phase_manager = get_project_phase_manager()
        self.workflow = get_mandatory_workflow()

        # Projects storage
        self.projects: Dict[str, ClientProject] = {}

        # Event handlers
        self.on_phase_complete = []
        self.on_project_complete = []
        self.on_milestone = []


# Singleton
app_ctx.checklist_manager: Optional[ClientProjectChecklistManager] = None


def get_client_project_manager() -> ClientProjectChecklistManager:
    """Global manager instance"""
    if app_ctx.checklist_manager is None:
        app_ctx.checklist_manager = ClientProjectChecklistManager()
    return app_ctx.checklist_manager


# Quick API functions
async def create_branding_project(
    client_name: str, services: List[str], **kwargs
) -> Dict[str, Any]:
    """Tezkor loyiha yaratish"""

    manager = get_client_project_manager()

    # Convert string to ServiceType
    service_map = {
        "brand_audit": ServiceType.BRAND_AUDIT,
        "naming_check": ServiceType.NAMING_CHECK,
        "naming": ServiceType.NAMING,
        "logo": ServiceType.LOGO,
        "visual_identity": ServiceType.VISUAL_IDENTITY,
        "brandbook": ServiceType.BRANDBOOK,
        "packaging": ServiceType.PACKAGING,
        "patent_support": ServiceType.PATENT_SUPPORT,
    }

    selected = [service_map[s] for s in services if s in service_map]

    return manager.create_project(
        client_name=client_name, selected_services=selected, **kwargs
    )


async def get_project_status(project_id: str) -> Optional[Dict]:
    """Loyiha statusini olish"""
    manager = get_client_project_manager()
    return manager.get_project_checklist(project_id)


async def complete_project_phase(
    project_id: str, phase_id: str, user_id: str, notes: str = ""
) -> Dict[str, Any]:
    """Loyiha bosqichini yakunlash"""
    manager = get_client_project_manager()
    return manager.complete_phase(
        project_id=project_id,
        phase_id=phase_id,
        user_id=user_id,
        evidence={"notes": notes},
    )
