"""
Phase template generator across project types.
"""
from __future__ import annotations

from typing import List
from src.services.phases.design_subphases_branding import add_branding_phases
from src.services.phases.design_subphases_media import add_media_phases
from src.services.phases.models import PhaseRole, ProjectPhase


def _build_pm_initial_phases() -> List[ProjectPhase]:
    return [
        ProjectPhase(id="PM1", name="Project Kickoff & Brief Audit", name_uz="Loyiha boshlanishi va brif auditi", description="Brifni to'liq o'rganish va talablarni aniqlashtirish", role=PhaseRole.PROJECT_MANAGER, service_type="all", estimated_minutes=45),
        ProjectPhase(id="PM2", name="Client Onboarding Call", name_uz="Mijoz bilan kirish suhbati", description="Strategiya va maqsadlarni kelishib olish", role=PhaseRole.PROJECT_MANAGER, service_type="all", estimated_minutes=30, depends_on=["PM1"]),
    ]


def _build_brandbook_and_packaging_phases(services: List[str]) -> List[ProjectPhase]:
    phases = []
    if "brandbook" in services or "brand_guidelines" in services:
        phases.extend([
            ProjectPhase(id="BB1", name="Brand Guidelines Structure", name_uz="Brandbook strukturasi", description="Mundarija va asosiy bo'limlar", role=PhaseRole.DESIGNER, service_type="brandbook", estimated_minutes=60, depends_on=["PM2"]),
            ProjectPhase(id="BB2", name="Brandbook Layout & Export", name_uz="Brandbook maketi va eksport", description="To'liq PDF qo'llanma tayyorlash", role=PhaseRole.DESIGNER, service_type="brandbook", estimated_minutes=240, depends_on=["BB1"]),
        ])
    if "packaging" in services:
        phases.extend([
            ProjectPhase(id="PKG1", name="Dieline & Architecture", name_uz="Qadoq qolipi va arxitekturasi", description="Qadoq o'lchamlari va chizmasi", role=PhaseRole.DESIGNER, service_type="packaging", estimated_minutes=90, depends_on=["PM2"]),
            ProjectPhase(id="PKG2", name="Packaging Graphic Design", name_uz="Qadoq grafik dizayni", description="Yuz va orqa qism dizayni", role=PhaseRole.DESIGNER, service_type="packaging", estimated_minutes=180, depends_on=["PKG1"]),
        ])
    return phases


def _build_closing_phases() -> List[ProjectPhase]:
    return [
        ProjectPhase(id="PM3", name="Quality Assurance & Asset Verification", name_uz="Sifat nazorati va fayllar tekshiruvi", description="Barcha yakuniy fayllarni tekshirish", role=PhaseRole.PROJECT_MANAGER, service_type="all", estimated_minutes=30),
        ProjectPhase(id="PM4", name="Final Handover & Client Approval", name_uz="Yakuniy topshirish va qabul dalolatnomasi", description="Litsenziya va shartnomani yopish", role=PhaseRole.PROJECT_MANAGER, service_type="all", estimated_minutes=30, depends_on=["PM3"]),
    ]


def build_phase_templates(services: List[str], project_name: str = "") -> List[ProjectPhase]:
    """Generates standard sequential ProjectPhase roadmap."""
    phases = _build_pm_initial_phases()
    service_str = " ".join(services).lower()

    add_branding_phases(services, phases, service_str)
    phases.extend(_build_brandbook_and_packaging_phases(services))
    add_media_phases(services, phases, service_str)
    phases.extend(_build_closing_phases())

    return phases
