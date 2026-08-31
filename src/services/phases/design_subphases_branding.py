"""
Logo and Naming design sub-phase definitions.
"""
from __future__ import annotations

from typing import List
from src.services.phases.models import PhaseRole, ProjectPhase


def _get_naming_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="N1", name="Naming Longlist", name_uz="Nomlar uzun ro'yxati", description="30+ ta nom varianti yaratish", role=PhaseRole.COPYWRITER, service_type="naming", estimated_minutes=120, depends_on=[last_pm]),
        ProjectPhase(id="N2", name="Linguistic & Legal Check", name_uz="Lingvistik va huquqiy tekshiruv", description="Dastlabki tovar belgisi va ma'no tekshiruvi", role=PhaseRole.COPYWRITER, service_type="naming", estimated_minutes=90, depends_on=["N1"]),
        ProjectPhase(id="N3", name="Naming Shortlist Presentation", name_uz="Nomlar shortlist prezentatsiyasi", description="5 ta saralangan nom konsepti bilan", role=PhaseRole.COPYWRITER, service_type="naming", estimated_minutes=60, depends_on=["N2"]),
    ]


def _get_logo_phases(last_pm: str) -> List[ProjectPhase]:
    return [
        ProjectPhase(id="L1", name="Moodboard & Visual Direction", name_uz="Moodboard va vizual yo'nalish", description="3 xil vizual uslub yo'nalishini belgilash", role=PhaseRole.ART_DIRECTOR, service_type="logo_design", estimated_minutes=60, depends_on=[last_pm]),
        ProjectPhase(id="L2", name="Logo Sketching & Concepts", name_uz="Logo eskizlari va konseptlar", description="3 ta xilma-xil logo konseptini chizish", role=PhaseRole.DESIGNER, service_type="logo_design", estimated_minutes=180, depends_on=["L1"]),
        ProjectPhase(id="L3", name="Concept Vectorization", name_uz="Konseptlarni vektorga o'tkazish", description="Tanlangan eskizlarni raqamlashtirish", role=PhaseRole.DESIGNER, service_type="logo_design", estimated_minutes=120, depends_on=["L2"]),
        ProjectPhase(id="L4", name="Logo Client Presentation", name_uz="Logo prezentatsiyasi", description="PDF prezentatsiya tayyorlash", role=PhaseRole.DESIGNER, service_type="logo_design", estimated_minutes=60, depends_on=["L3"]),
        ProjectPhase(id="L5", name="Logo Revisions", name_uz="Logo tuzatishlari", description="Mijoz fikrlari asosida tuzatish kiritish", role=PhaseRole.DESIGNER, service_type="logo_design", estimated_minutes=90, depends_on=["L4"]),
        ProjectPhase(id="L6", name="Final Logo Files Prep", name_uz="Final logo fayllarini tayyorlash", description="AI, EPS, SVG, PNG, PDF formatlar", role=PhaseRole.DESIGNER, service_type="logo_design", estimated_minutes=60, depends_on=["L5"]),
    ]


def add_branding_phases(services: List[str], phases: List[ProjectPhase], service_str: str) -> None:
    last_pm = "PM2"
    if "naming" in services:
        phases.extend(_get_naming_phases(last_pm))
    if "logo_design" in services or "branding" in services:
        phases.extend(_get_logo_phases(last_pm))
