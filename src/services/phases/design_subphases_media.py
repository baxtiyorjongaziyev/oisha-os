"""
SMM, Web, 3D, Motion, Presentation, and Print design sub-phase definitions.
"""
from typing import List
from src.services.phases.models import PhaseRole, PhaseStatus, ProjectPhase


def add_media_phases(services: List[str], phases: List[ProjectPhase], service_str: str) -> None:
    if "visual_identity" in services:
        visual_depends = last_pm_phase
        phases.extend(
            [
                ProjectPhase(
                    id="V1",
                    name="Color Palette",
                    name_uz="Rang palitrasu",
                    description="Rang palitrasini tanlash (3 ta variant)",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=60,
                    depends_on=[visual_depends],
                ),
                ProjectPhase(
                    id="V2",
                    name="Typography",
                    name_uz="Typography",
                    description="Typography sistemasini tanlash",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=45,
                    depends_on=["V1"],
                ),
                ProjectPhase(
                    id="V3",
                    name="Graphic Elements",
                    name_uz="Grafik elementlar",
                    description="Grafik elementlarni yaratish (pattern, shape)",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=90,
                    depends_on=["V2"],
                ),
                ProjectPhase(
                    id="V4",
                    name="Photography Style",
                    name_uz="Photography style",
                    description="Photography style guide",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=45,
                    depends_on=["V3"],
                ),
                ProjectPhase(
                    id="V5",
                    name="Icon Set",
                    name_uz="Icon set",
                    description="Icon set yaratish (20 ta)",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=120,
                    depends_on=["V4"],
                ),
                ProjectPhase(
                    id="V6",
                    name="VI Rules",
                    name_uz="VI qoidalari",
                    description="Visual identity qoidalarini yozish",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=60,
                    depends_on=["V5"],
                ),
                ProjectPhase(
                    id="V7",
                    name="VI Approval",
                    name_uz="VI tasdiqlash",
                    description="PM va mijozdan tasdiqlash",
                    role=PhaseRole.DESIGNER,
                    service_type="visual_identity",
                    estimated_minutes=30,
                    depends_on=["V6"],
                    requires_client_approval=True,
                ),
            ]
        )
        last_pm_phase = "V7"

    # Brandbook
    if "brandbook" in services:
        brandbook_depends = last_pm_phase
        phases.extend(
            [
                ProjectPhase(
                    id="B1",
                    name="BB Structure",
                    name_uz="BB struktura",
                    description="Brandbook strukturasini rejalashtirish",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=30,
                    depends_on=[brandbook_depends],
                ),
                ProjectPhase(
                    id="B2",
                    name="Collect Materials",
                    name_uz="Material yig'ish",
                    description="Mavjud materiallarni yig'ish (logo, visual)",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=30,
                    depends_on=["B1"],
                ),
                ProjectPhase(
                    id="B3",
                    name="Brand Strategy",
                    name_uz="Brand strategiya",
                    description="Brand strategy qismini yozish",
                    role=PhaseRole.COPYWRITER,
                    service_type="brandbook",
                    estimated_minutes=60,
                    depends_on=["B2"],
                ),
                ProjectPhase(
                    id="B4",
                    name="Logo Guidelines",
                    name_uz="Logo qo'llanma",
                    description="Logo usage guidelines",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=60,
                    depends_on=["B3"],
                ),
                ProjectPhase(
                    id="B5",
                    name="Color & Type Rules",
                    name_uz="Rang va type qoidalari",
                    description="Color system va typography qoidalari",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=45,
                    depends_on=["B4"],
                ),
                ProjectPhase(
                    id="B6",
                    name="Visual Applications",
                    name_uz="Visual application",
                    description="Visual applications (vizitka, blank, konvert)",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=120,
                    depends_on=["B5"],
                ),
                ProjectPhase(
                    id="B7",
                    name="Mockups",
                    name_uz="Mockup'lar",
                    description="Mockup'larni yaratish",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=90,
                    depends_on=["B6"],
                ),
                ProjectPhase(
                    id="B8",
                    name="BB Design",
                    name_uz="BB dizayn",
                    description="Brandbook dizayni va layout",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=180,
                    depends_on=["B7"],
                ),
                ProjectPhase(
                    id="B9",
                    name="BB Approval",
                    name_uz="BB tasdiqlash",
                    description="PM va mijozdan tasdiqlash",
                    role=PhaseRole.DESIGNER,
                    service_type="brandbook",
                    estimated_minutes=30,
                    depends_on=["B8"],
                    requires_client_approval=True,
                ),
            ]
        )
        last_pm_phase = "B9"

    # Packaging
    if "packaging" in services:
        packaging_depends = last_pm_phase
        phases.extend(
            [
                ProjectPhase(
                    id="Q1",
                    name="Pack Brief",
                    name_uz="Qadoq brief",
                    description="Qadoq talablarini tushunish",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=20,
                    depends_on=[packaging_depends],
                ),
                ProjectPhase(
                    id="Q2",
                    name="Pack Research",
                    name_uz="Qadoq research",
                    description="O'xshash qadoqlarni research qilish",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=45,
                    depends_on=["Q1"],
                ),
                ProjectPhase(
                    id="Q3",
                    name="Pack Concepts",
                    name_uz="Qadoq konsepsiya",
                    description="3 ta qadoq konsepsiyasi",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=90,
                    depends_on=["Q2"],
                ),
                ProjectPhase(
                    id="Q4",
                    name="Dieline",
                    name_uz="Dieline",
                    description="Dieline yaratish (texnik chizma)",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=60,
                    depends_on=["Q3"],
                ),
                ProjectPhase(
                    id="Q5",
                    name="3D Mockup",
                    name_uz="3D mockup",
                    description="3D mockup yaratish",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=60,
                    depends_on=["Q4"],
                ),
                ProjectPhase(
                    id="Q6",
                    name="Pack Approval",
                    name_uz="Qadoq tasdiqlash",
                    description="Mijozdan tasdiqlash",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=30,
                    depends_on=["Q5"],
                    requires_client_approval=True,
                ),
                ProjectPhase(
                    id="Q7",
                    name="Print Files",
                    name_uz="Print fayllar",
                    description="Print uchun final fayllar tayyorlash",
                    role=PhaseRole.DESIGNER,
                    service_type="packaging",
                    estimated_minutes=45,
                    depends_on=["Q6"],
                ),
            ]
        )
        last_pm_phase = "Q7"

    # Patent Support
    if "patent_support" in services:
        patent_depends = last_pm_phase
        phases.extend(
            [
                ProjectPhase(
                    id="PT1",
                    name="Doc Collection",
                    name_uz="Dokumentatsiya",
                    description="Logo va brand elementlarini dokumentatsiya qilish",
                    role=PhaseRole.DESIGNER,
                    service_type="patent",
                    estimated_minutes=30,
                    depends_on=[patent_depends],
                ),
                ProjectPhase(
                    id="PT2",
                    name="Patent Files",
                    name_uz="Patent fayllar",
                    description="Patent uchun kerakli fayllarni tayyorlash",
                    role=PhaseRole.DESIGNER,
                    service_type="patent",
                    estimated_minutes=45,
                    depends_on=["PT1"],
                ),
                ProjectPhase(
                    id="PT3",
                    name="Patent Referral",
                    name_uz="Patent yo'naltirish",
                    description="Mijozga Uzpatent yoki yuristga yo'naltirish",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="patent",
                    estimated_minutes=15,
                    depends_on=["PT2"],
                ),
            ]
        )

    return phases
