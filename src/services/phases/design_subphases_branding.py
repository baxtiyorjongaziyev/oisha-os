"""
Branding, naming, logo, and identity design sub-phase definitions.
"""
from typing import List
from src.services.phases.models import PhaseRole, PhaseStatus, ProjectPhase


def add_branding_phases(services: List[str], phases: List[ProjectPhase], service_str: str) -> None:
    last_pm_phase = "P6"

    # Brand Audit
    if "brand_audit" in services:
        phases.extend(
            [
                ProjectPhase(
                    id="D1",
                    name="Understand Brief",
                    name_uz="Briefni tushunish",
                    description="Brief olish (PM'dan)",
                    role=PhaseRole.DESIGNER,
                    service_type="brand_audit",
                    estimated_minutes=20,
                    depends_on=[last_pm_phase],
                ),
                ProjectPhase(
                    id="D2",
                    name="Industry Research",
                    name_uz="Soha tadqiqi",
                    description="Mijoz sohasini va raqobatchilarni tadqiq qilish",
                    role=PhaseRole.DESIGNER,
                    service_type="brand_audit",
                    estimated_minutes=60,
                    depends_on=["D1"],
                ),
                ProjectPhase(
                    id="D3",
                    name="Brand Analysis",
                    name_uz="Brand tahlili",
                    description="Mijozning hozirgi brandini tahlil qilish",
                    role=PhaseRole.DESIGNER,
                    service_type="brand_audit",
                    estimated_minutes=45,
                    depends_on=["D2"],
                ),
                ProjectPhase(
                    id="D4",
                    name="SWOT Analysis",
                    name_uz="SWOT analiz",
                    description="SWOT analizi va tavsiyalar",
                    role=PhaseRole.DESIGNER,
                    service_type="brand_audit",
                    estimated_minutes=30,
                    depends_on=["D3"],
                ),
                ProjectPhase(
                    id="D5",
                    name="Audit Report",
                    name_uz="Audit hisoboti",
                    description="Brand audit hisobotini yaratish",
                    role=PhaseRole.DESIGNER,
                    service_type="brand_audit",
                    estimated_minutes=60,
                    depends_on=["D4"],
                ),
                ProjectPhase(
                    id="D6",
                    name="Report Approval",
                    name_uz="Hisobot tasdiqlash",
                    description="PM va mijozdan tasdiqlash olish",
                    role=PhaseRole.DESIGNER,
                    service_type="brand_audit",
                    estimated_minutes=30,
                    depends_on=["D5"],
                    requires_client_approval=True,
                ),
            ]
        )
        last_pm_phase = "D6"

    # Naming
    if "naming" in services:
        naming_depends = last_pm_phase
        phases.extend(
            [
                ProjectPhase(
                    id="N1",
                    name="Naming Brief",
                    name_uz="Naming brief",
                    description="Naming briefini tushunish",
                    role=PhaseRole.COPYWRITER,
                    service_type="naming",
                    estimated_minutes=15,
                    depends_on=[naming_depends],
                ),
                ProjectPhase(
                    id="N2",
                    name="Competitor Check",
                    name_uz="Konkurent tekshiruv",
                    description="Konkurent nomlarini tekshirish",
                    role=PhaseRole.COPYWRITER,
                    service_type="naming",
                    estimated_minutes=30,
                    depends_on=["N1"],
                ),
                ProjectPhase(
                    id="N3",
                    name="Create Names",
                    name_uz="Nom yaratish",
                    description="30 ta nom variantini yaratish",
                    role=PhaseRole.COPYWRITER,
                    service_type="naming",
                    estimated_minutes=90,
                    depends_on=["N2"],
                ),
                ProjectPhase(
                    id="N4",
                    name="Trademark Check",
                    name_uz="Trademark tekshiruv",
                    description="Trademark tekshiruvi (USPTO, Uzpatent)",
                    role=PhaseRole.COPYWRITER,
                    service_type="naming",
                    estimated_minutes=60,
                    depends_on=["N3"],
                ),
                ProjectPhase(
                    id="N5",
                    name="Select Top 3",
                    name_uz="3 ta tanlash",
                    description="3 ta eng yaxshi variantni tanlash",
                    role=PhaseRole.COPYWRITER,
                    service_type="naming",
                    estimated_minutes=30,
                    depends_on=["N4"],
                ),
                ProjectPhase(
                    id="N6",
                    name="Client Approval",
                    name_uz="Mijoz tasdiqlash",
                    description="Mijozdan tasdiqlash olish",
                    role=PhaseRole.COPYWRITER,
                    service_type="naming",
                    estimated_minutes=30,
                    depends_on=["N5"],
                    requires_client_approval=True,
                ),
            ]
        )
        last_pm_phase = "N6"

    # Logo
    if "logo" in services:
        logo_depends = last_pm_phase
        phases.extend(
            [
                ProjectPhase(
                    id="L1",
                    name="Logo Research",
                    name_uz="Logo research",
                    description="Research va moodboard (3 ta yo'nalish)",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=90,
                    depends_on=[logo_depends],
                ),
                ProjectPhase(
                    id="L2",
                    name="Sketch Concepts",
                    name_uz="Eskiz konsepsiya",
                    description="3 ta turli konsepsiya eskizi",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=120,
                    depends_on=["L1"],
                ),
                ProjectPhase(
                    id="L3",
                    name="Digital Concepts",
                    name_uz="Digital konsepsiya",
                    description="3 ta konsepsiyani digital ko'rinishda chizish",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=180,
                    depends_on=["L2"],
                ),
                ProjectPhase(
                    id="L4",
                    name="Usage Rules",
                    name_uz="Qo'llanma qoidalari",
                    description="Logo qoidalarini yozish (qayerda qo'llash mumkin)",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=30,
                    depends_on=["L3"],
                ),
                ProjectPhase(
                    id="L5",
                    name="Concept Selection",
                    name_uz="Konsepsiya tanlash",
                    description="PM va mijozdan 1 ta konsepsiya tanlash",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=30,
                    depends_on=["L4"],
                    requires_client_approval=True,
                ),
                ProjectPhase(
                    id="L6",
                    name="Refine Logo",
                    name_uz="Logoni rivojlantirish",
                    description="Tanlangan konsepsiyani rivojlantirish (3 iteratsiya)",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=240,
                    depends_on=["L5"],
                ),
                ProjectPhase(
                    id="L7",
                    name="Final Logo",
                    name_uz="Yakuniy logo",
                    description="Yakuniy logo va variantlarini tayyorlash",
                    role=PhaseRole.DESIGNER,
                    service_type="logo",
                    estimated_minutes=60,
                    depends_on=["L6"],
                ),
            ]
        )
        last_pm_phase = "L7"
