"""
SMM, Web, 3D, Motion, Presentation, and Print design sub-phase definitions.
"""
from __future__ import annotations

from typing import List
from src.services.phases.models import PhaseRole, ProjectPhase


def _get_visual_identity_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="V1", name="Color Palette", name_uz="Rang palitrasi", description="Rang palitrasini tanlash", role=PhaseRole.DESIGNER, service_type="visual_identity", estimated_minutes=60, depends_on=[last_pm]),
        ProjectPhase(id="V2", name="Typography", name_uz="Typography", description="Typography sistemasini tanlash", role=PhaseRole.DESIGNER, service_type="visual_identity", estimated_minutes=45, depends_on=["V1"]),
        ProjectPhase(id="V3", name="Graphic Elements", name_uz="Grafik elementlar", description="Grafik elementlarni yaratish", role=PhaseRole.DESIGNER, service_type="visual_identity", estimated_minutes=90, depends_on=["V2"]),
        ProjectPhase(id="V4", name="Photography Style", name_uz="Photography style", description="Photography style guide", role=PhaseRole.DESIGNER, service_type="visual_identity", estimated_minutes=45, depends_on=["V3"]),
        ProjectPhase(id="V5", name="Icon Set", name_uz="Icon set", description="Icon set yaratish (20 ta)", role=PhaseRole.DESIGNER, service_type="visual_identity", estimated_minutes=120, depends_on=["V4"]),
    ]


def _get_smm_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="S1", name="SMM Grid Concept", name_uz="SMM grid konsept", description="Instagram grid konsepti (9 ta post)", role=PhaseRole.DESIGNER, service_type="smm_design", estimated_minutes=120, depends_on=[last_pm]),
        ProjectPhase(id="S2", name="Post Templates", name_uz="Post shablonlari", description="Post shablonlarini yaratish (5 ta)", role=PhaseRole.DESIGNER, service_type="smm_design", estimated_minutes=90, depends_on=["S1"]),
        ProjectPhase(id="S3", name="Stories Templates", name_uz="Stories shablonlari", description="Stories shablonlarini yaratish (5 ta)", role=PhaseRole.DESIGNER, service_type="smm_design", estimated_minutes=60, depends_on=["S2"]),
        ProjectPhase(id="S4", name="Highlights Covers", name_uz="Highlights muqovalari", description="Highlights covers (8 ta)", role=PhaseRole.DESIGNER, service_type="smm_design", estimated_minutes=45, depends_on=["S3"]),
    ]


def _get_web_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="W1", name="Wireframes", name_uz="Wireframe lar", description="UX wireframelarni chizish", role=PhaseRole.DESIGNER, service_type="web_design", estimated_minutes=180, depends_on=[last_pm]),
        ProjectPhase(id="W2", name="UI Design (Desktop)", name_uz="UI dizayn (Desktop)", description="Desktop versiya UI dizayni", role=PhaseRole.DESIGNER, service_type="web_design", estimated_minutes=240, depends_on=["W1"]),
        ProjectPhase(id="W3", name="UI Design (Mobile)", name_uz="UI dizayn (Mobile)", description="Mobil versiya UI dizayni", role=PhaseRole.DESIGNER, service_type="web_design", estimated_minutes=120, depends_on=["W2"]),
        ProjectPhase(id="W4", name="Design System", name_uz="Dizayn sistema", description="Web design system (komponentlar)", role=PhaseRole.DESIGNER, service_type="web_design", estimated_minutes=90, depends_on=["W3"]),
    ]


def _get_motion_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="M1", name="Storyboard", name_uz="Storyboard", description="Animatsiya storyboardi", role=PhaseRole.MOTION_DESIGNER, service_type="motion_design", estimated_minutes=90, depends_on=[last_pm]),
        ProjectPhase(id="M2", name="Logo Animation", name_uz="Logo animatsiyasi", description="Logo animatsiyasini tayyorlash", role=PhaseRole.MOTION_DESIGNER, service_type="motion_design", estimated_minutes=180, depends_on=["M1"]),
        ProjectPhase(id="M3", name="Reels/Promo Video", name_uz="Reels/Promo video", description="Promo video tayyorlash (15-30s)", role=PhaseRole.MOTION_DESIGNER, service_type="motion_design", estimated_minutes=240, depends_on=["M2"]),
    ]


def _get_presentation_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="PR1", name="Master Slide Design", name_uz="Asosiy slayd dizayni", description="Prezentatsiya master shabloni", role=PhaseRole.DESIGNER, service_type="presentation", estimated_minutes=90, depends_on=[last_pm]),
        ProjectPhase(id="PR2", name="Slide Layouts", name_uz="Slaydlar maketi", description="Barcha slaydlarni tayyorlash (15-20 slayd)", role=PhaseRole.DESIGNER, service_type="presentation", estimated_minutes=180, depends_on=["PR1"]),
        ProjectPhase(id="PR3", name="Infographics", name_uz="Infografika", description="Prezentatsiya infografikalari", role=PhaseRole.DESIGNER, service_type="presentation", estimated_minutes=90, depends_on=["PR2"]),
    ]


def _get_3d_and_print_phases(services: List[str], last_pm: str) -> List[ProjectPhase]:
    phases = []
    if "3d_design" in services:
        phases.extend([
            ProjectPhase(id="3D1", name="3D Modeling", name_uz="3D modellashtirish", description="3D model yaratish", role=PhaseRole.DESIGNER, service_type="3d_design", estimated_minutes=240, depends_on=[last_pm]),
            ProjectPhase(id="3D2", name="3D Rendering", name_uz="3D render", description="Render va yorug'lik sozlamalari", role=PhaseRole.DESIGNER, service_type="3d_design", estimated_minutes=180, depends_on=["3D1"]),
        ])
    if "print_design" in services:
        phases.extend([
            ProjectPhase(id="P1", name="Print Collateral", name_uz="Poligrafiya materiallari", description="Vizitka, blank, konvert, papka", role=PhaseRole.DESIGNER, service_type="print_design", estimated_minutes=120, depends_on=[last_pm]),
            ProjectPhase(id="P2", name="Pre-press Prep", name_uz="Pechatga tayyorlash", description="Chop etishga texnik tayyorlash (CMYK, bleed)", role=PhaseRole.DESIGNER, service_type="print_design", estimated_minutes=60, depends_on=["P1"]),
        ])
    return phases


def add_media_phases(services: List[str], phases: List[ProjectPhase], service_str: str) -> None:
    last_pm = "PM2"
    if "visual_identity" in services:
        phases.extend(_get_visual_identity_phases(last_pm))
    if "smm_design" in services:
        phases.extend(_get_smm_phases(last_pm))
    if "web_design" in services:
        phases.extend(_get_web_phases(last_pm))
    if "motion_design" in services:
        phases.extend(_get_motion_phases(last_pm))
    if "presentation" in services:
        phases.extend(_get_presentation_phases(last_pm))
    phases.extend(_get_3d_and_print_phases(services, last_pm))
