"""
ProjectPhaseManager and singleton accessor.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.context import app_ctx
from src.services.phases.models import PhaseRole, PhaseStatus, ProjectChecklist, ProjectPhase
from src.services.phases.templates import build_phase_templates
from src.services.phases.design_phases import build_design_phases

logger = logging.getLogger(__name__)


class ProjectPhaseManager:
    """
    Loyiha bosqichlarini boshqarish va nazorat qilish tizimi.
    """

    def __init__(self):
        self.phase_templates = build_phase_templates()
        self.active_projects: Dict[str, ProjectChecklist] = {}

    def _setup_phase_templates(self):
        self.phase_templates = build_phase_templates()

    def _create_design_phases(self, services: List[str]) -> List[ProjectPhase]:
        return build_design_phases(services)

    def create_checklist(
        self,
        project_id: str,
        project_name: str,
        services: List[str],
        start_date: Optional[datetime] = None,
    ) -> ProjectChecklist:
        """Yangi loyiha uchun checklist yaratish."""
        phases: List[ProjectPhase] = []
        phase_order = 1

        onboarding = [
            ProjectPhase(
                id=f"{project_id}_onb_1",
                name="Loyiha brifingi va ma'lumot to'plash",
                role=PhaseRole.PM,
                service="Onboarding",
                order=phase_order,
                checklist=["Brifing o'tkazish", "Materiallarni qabul qilish", "Guruh ochish"],
            ),
            ProjectPhase(
                id=f"{project_id}_onb_2",
                name="Texnik topshiriq (TZ) tayyorlash",
                role=PhaseRole.PM,
                service="Onboarding",
                order=phase_order + 1,
                dependencies=[f"{project_id}_onb_1"],
                checklist=["TZ yozish", "Mijoz bilan tasdiqlash"],
            ),
        ]
        phases.extend(onboarding)
        phase_order += len(onboarding)

        design_phases = self._create_design_phases(services)
        for p in design_phases:
            p.id = f"{project_id}_{p.id}"
            p.order = phase_order
            phase_order += 1
            phases.append(p)

        closeout = [
            ProjectPhase(
                id=f"{project_id}_close_1",
                name="Final materiallarni topshirish",
                role=PhaseRole.PM,
                service="Closeout",
                order=phase_order,
                checklist=["Barcha fayllarni tartiblash", "Drive havolasini yuborish"],
            ),
            ProjectPhase(
                id=f"{project_id}_close_2",
                name="Loyiha yopilishi va feedback",
                role=PhaseRole.PM,
                service="Closeout",
                order=phase_order + 1,
                dependencies=[f"{project_id}_close_1"],
                checklist=["NPS so'rovnoma", "Case study tayyorlash", "Hisob-kitobni yopish"],
            ),
        ]
        phases.extend(closeout)

        checklist = ProjectChecklist(
            project_id=project_id,
            project_name=project_name,
            services=services,
            phases=phases,
            start_date=start_date or datetime.now(timezone.utc),
        )
        self.active_projects[project_id] = checklist
        return checklist

    def start_phase(self, project_id: str, phase_id: str) -> bool:
        checklist = self.active_projects.get(project_id)
        if not checklist:
            return False
        for phase in checklist.phases:
            if phase.id == phase_id:
                if not phase.can_start():
                    logger.warning(f"Bosqich boshlanishi mumkin emas: {phase.name}")
                    return False
                phase.status = PhaseStatus.IN_PROGRESS
                phase.started_at = datetime.now(timezone.utc)
                return True
        return False

    def complete_phase(
        self,
        project_id: str,
        phase_id: str,
        completed_by: str,
        deliverables: Optional[List[str]] = None,
    ) -> bool:
        checklist = self.active_projects.get(project_id)
        if not checklist:
            return False
        for phase in checklist.phases:
            if phase.id == phase_id:
                phase.status = PhaseStatus.COMPLETED
                phase.completed_at = datetime.now(timezone.utc)
                phase.completed_by = completed_by
                if deliverables:
                    phase.deliverables.extend(deliverables)

                # Next phase unlock
                for next_p in checklist.phases:
                    if phase_id in next_p.dependencies and next_p.can_start():
                        if next_p.status == PhaseStatus.PENDING:
                            logger.info(f"Keyingi bosqich ochildi: {next_p.name}")
                return True
        return False

    def get_checklist(self, project_id: str) -> Optional[ProjectChecklist]:
        return self.active_projects.get(project_id)

    def get_project_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        checklist = self.active_projects.get(project_id)
        if not checklist:
            return None
        progress = checklist.get_progress()
        next_pending = checklist.get_next_pending()
        return {
            "project_name": checklist.project_name,
            "progress": progress,
            "next_phase": next_pending.name if next_pending else "Barcha bosqichlar tugallangan",
            "next_role": next_pending.role.value if next_pending else None,
        }


def get_project_phase_manager() -> ProjectPhaseManager:
    if getattr(app_ctx, "phase_manager", None) is None:
        app_ctx.phase_manager = ProjectPhaseManager()
    return app_ctx.phase_manager
