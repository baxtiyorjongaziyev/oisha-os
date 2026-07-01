"""
Project Phases - Loyiha bosqichlarini boshqarish
Jon.Branding - Branding loyihalari uchun to'liq qadamlar tizimi
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


class PhaseStatus(Enum):
    """Bosqich statuslari"""

    LOCKED = "locked"  # Bloklangan (oldingisi bajarilmagan)
    PENDING = "pending"  # Kutilmoqda
    IN_PROGRESS = "in_progress"  # Bajarilmoqda
    REVIEW = "review"  # Tekshiruvda (PM/Director)
    COMPLETED = "completed"  # Bajarildi
    SKIPPED = "skipped"  # O'tkazib yuborildi


class PhaseRole(Enum):
    """Bosqichni bajaruvchi rol"""

    HUNTER = "hunter"
    SETTER = "setter"
    CLOSER = "closer"
    PROJECT_MANAGER = "pm"
    DESIGNER = "designer"
    COPYWRITER = "copywriter"
    CLIENT = "client"  # Mijoz tasdiqlashi kerak


@dataclass
class ProjectPhase:
    """Loyiha bosqichi"""

    id: str
    name: str
    name_uz: str
    description: str
    role: PhaseRole
    service_type: str  # logo, visual_identity, brandbook, etc.

    # Vaqt
    estimated_minutes: int

    # Zavisimost
    depends_on: List[str] = field(default_factory=list)

    # Status
    status: PhaseStatus = PhaseStatus.LOCKED

    # Tekshirish
    requires_client_approval: bool = False
    requires_pm_approval: bool = False

    # Evidence
    deliverables: List[str] = field(default_factory=list)

    # AmoCRM
    crm_stage_id: Optional[int] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None

    # Evidence files
    attachments: List[Dict] = field(default_factory=list)
    notes: str = ""

    def can_start(self, completed_phases: List[str]) -> bool:
        """Bosqichni boshlash mumkinmi?"""
        if not self.depends_on:
            return True
        return all(dep in completed_phases for dep in self.depends_on)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_uz": self.name_uz,
            "description": self.description,
            "role": self.role.value,
            "service_type": self.service_type,
            "estimated_minutes": self.estimated_minutes,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "requires_client_approval": self.requires_client_approval,
            "requires_pm_approval": self.requires_pm_approval,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class ProjectChecklist:
    """Loyiha checklisti"""

    project_id: str
    client_name: str
    client_id: Optional[str] = None

    # Xizmatlar
    services: List[str] = field(default_factory=list)

    # Bosqichlar
    phases: List[ProjectPhase] = field(default_factory=list)

    # Status
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Timing
    total_estimated_days: int = 0
    deadline: Optional[datetime] = None

    def get_phases_by_role(self, role: PhaseRole) -> List[ProjectPhase]:
        """Rol bo'yicha bosqichlarni olish"""
        return [p for p in self.phases if p.role == role]

    def get_phases_by_service(self, service: str) -> List[ProjectPhase]:
        """Xizmat bo'yicha bosqichlarni olish"""
        return [p for p in self.phases if p.service_type == service]

    def get_next_pending(self) -> Optional[ProjectPhase]:
        """Keyingi bajarilishi kerak bosqich"""
        completed = [p.id for p in self.phases if p.status == PhaseStatus.COMPLETED]

        for phase in sorted(self.phases, key=lambda p: p.id):
            if (
                phase.status == PhaseStatus.PENDING
                or phase.status == PhaseStatus.LOCKED
            ):
                if phase.can_start(completed):
                    return phase
        return None

    def get_progress(self) -> Dict[str, Any]:
        """Progress statistikasi"""
        total = len(self.phases)
        completed = len([p for p in self.phases if p.status == PhaseStatus.COMPLETED])
        in_progress = len(
            [p for p in self.phases if p.status == PhaseStatus.IN_PROGRESS]
        )
        locked = len([p for p in self.phases if p.status == PhaseStatus.LOCKED])
        pending = len([p for p in self.phases if p.status == PhaseStatus.PENDING])

        return {
            "total_phases": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "locked": locked,
            "percentage": round((completed / total * 100), 1) if total > 0 else 0,
        }


class ProjectPhaseManager:
    """
    Loyiha bosqichlarini boshqarish tizimi

    Har bir xizmat turiga qarab bosqichlar yaratadi va
    ketma-ket bajarilishini nazorat qiladi.
    """

    def __init__(self):
        self.checklists: Dict[str, ProjectChecklist] = {}
        self.phase_templates: Dict[str, List[ProjectPhase]] = {}
        self._setup_phase_templates()

    def _setup_phase_templates(self):
        """Bosqich shablonlarini yaratish"""

        # HUNTER phases - Lead ovlash
        self.phase_templates["hunter"] = [
            ProjectPhase(
                id="H1",
                name="Daily Plan",
                name_uz="Kunlik rejani olish",
                description="Direktordan kunlik Surgical Mission olish",
                role=PhaseRole.HUNTER,
                service_type="hunter",
                estimated_minutes=15,
                crm_stage_id=53729371,
            ),
            ProjectPhase(
                id="H2",
                name="Lead Search",
                name_uz="Lead qidirish",
                description="50 ta yangi lead topish (Telegram, LinkedIn, Instagram)",
                role=PhaseRole.HUNTER,
                service_type="hunter",
                estimated_minutes=120,
                depends_on=["H1"],
            ),
            ProjectPhase(
                id="H3",
                name="First Contact",
                name_uz="Birinchi kontakt",
                description="20 ta lead bilan aloqa qilish (cold outreach)",
                role=PhaseRole.HUNTER,
                service_type="hunter",
                estimated_minutes=90,
                depends_on=["H2"],
            ),
            ProjectPhase(
                id="H4",
                name="CRM Upload",
                name_uz="CRM'ga yuklash",
                description="Branding qiziqadiganlarni ajratib, AmoCRM'ga yuklash",
                role=PhaseRole.HUNTER,
                service_type="hunter",
                estimated_minutes=30,
                depends_on=["H3"],
            ),
            ProjectPhase(
                id="H5",
                name="Daily Report",
                name_uz="Kunlik hisobot",
                description="Direktorga natijalar haqida hisobot",
                role=PhaseRole.HUNTER,
                service_type="hunter",
                estimated_minutes=15,
                depends_on=["H4"],
                requires_pm_approval=True,
            ),
        ]

        # SETTER phases - Uchrashuv belgilash
        self.phase_templates["setter"] = [
            ProjectPhase(
                id="S1",
                name="Lead Qualification",
                name_uz="Kvalifikatsiya tekshirish",
                description="CRM'dagi leadlarni saralash (qualified vs unqualified)",
                role=PhaseRole.SETTER,
                service_type="setter",
                estimated_minutes=30,
                crm_stage_id=53729376,
            ),
            ProjectPhase(
                id="S2",
                name="Cold Calls",
                name_uz="Qo'ng'iroq qilish",
                description="15 ta qualified leadga qo'ng'iroq qilish",
                role=PhaseRole.SETTER,
                service_type="setter",
                estimated_minutes=90,
                depends_on=["S1"],
            ),
            ProjectPhase(
                id="S3",
                name="Schedule Meetings",
                name_uz="Uchrashuv belgilash",
                description="Kamida 3 ta uchrashuv (strategy session) belgilash",
                role=PhaseRole.SETTER,
                service_type="setter",
                estimated_minutes=60,
                depends_on=["S2"],
                crm_stage_id=142,
            ),
            ProjectPhase(
                id="S4",
                name="Calendar Setup",
                name_uz="Kalendar tasdiqlash",
                description="Uchrashuvlarni kalendar'ga qo'shish va tasdiqlash",
                role=PhaseRole.SETTER,
                service_type="setter",
                estimated_minutes=15,
                depends_on=["S3"],
            ),
            ProjectPhase(
                id="S5",
                name="Send Reminders",
                name_uz="Eslatma yuborish",
                description="Mijozlarga uchrashuv eslatmasi yuborish",
                role=PhaseRole.SETTER,
                service_type="setter",
                estimated_minutes=15,
                depends_on=["S4"],
                crm_stage_id=143,
            ),
        ]

        # CLOSER phases - Bitim yopish
        self.phase_templates["closer"] = [
            ProjectPhase(
                id="C1",
                name="Client Research",
                name_uz="Mijoz research",
                description="Mijoz sayti va ijtimoiy tarmoqlarini research qilish",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=30,
            ),
            ProjectPhase(
                id="C2",
                name="Portfolio Prep",
                name_uz="Portfolio tayyorlash",
                description="Mos portfolio cases'ni tanlash",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=20,
                depends_on=["C1"],
            ),
            ProjectPhase(
                id="C3",
                name="Strategy Session",
                name_uz="Strategy Session",
                description="Uchrashuv o'tkazish (60 daqiqa)",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=60,
                depends_on=["C2"],
                crm_stage_id=53729384,
            ),
            ProjectPhase(
                id="C4",
                name="Brand Audit Proposal",
                name_uz="Brand audit taklifi",
                description="Brand audit taklifi yuborish (bepul yoki to'lovli)",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=30,
                depends_on=["C3"],
                crm_stage_id=53729385,
            ),
            ProjectPhase(
                id="C5",
                name="Commercial Proposal",
                name_uz="Kommersiya taklifi",
                description="Asosiy kommersiya taklifi yuborish",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=45,
                depends_on=["C4"],
            ),
            ProjectPhase(
                id="C6",
                name="Follow-up",
                name_uz="Follow-up",
                description="24 soat ichida follow-up qilish",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=15,
                depends_on=["C5"],
                crm_stage_id=53729386,
            ),
            ProjectPhase(
                id="C7",
                name="Close Deal",
                name_uz="Bitim yopish",
                description="Shartnoma imzolash va avans olish",
                role=PhaseRole.CLOSER,
                service_type="closer",
                estimated_minutes=30,
                depends_on=["C6"],
                crm_stage_id=53729390,
                requires_pm_approval=True,
            ),
        ]

        # PM phases - Loyiha boshqaruvi
        self.phase_templates["pm"] = [
            ProjectPhase(
                id="P1",
                name="Contract Review",
                name_uz="Shartnoma tekshirish",
                description="Shartnoma va to'lovni tasdiqlash",
                role=PhaseRole.PROJECT_MANAGER,
                service_type="pm",
                estimated_minutes=15,
            ),
            ProjectPhase(
                id="P2",
                name="Team Assignment",
                name_uz="Jamoa tayinlash",
                description="Designer va Copywriter ni loyihaga tayinlash",
                role=PhaseRole.PROJECT_MANAGER,
                service_type="pm",
                estimated_minutes=15,
                depends_on=["P1"],
            ),
            ProjectPhase(
                id="P3",
                name="Kickoff Meeting",
                name_uz="Kickoff meeting",
                description="Mijoz bilan kickoff meeting (30 daqiqa)",
                role=PhaseRole.PROJECT_MANAGER,
                service_type="pm",
                estimated_minutes=30,
                depends_on=["P2"],
            ),
            ProjectPhase(
                id="P4",
                name="Create Brief",
                name_uz="Brief yaratish",
                description="Detailed brief yaratish (mijoz ma'lumotlari bilan)",
                role=PhaseRole.PROJECT_MANAGER,
                service_type="pm",
                estimated_minutes=45,
                depends_on=["P3"],
            ),
            ProjectPhase(
                id="P5",
                name="Plan Timeline",
                name_uz="Timeline rejalashtirish",
                description="Timeline va deadline rejalashtirish",
                role=PhaseRole.PROJECT_MANAGER,
                service_type="pm",
                estimated_minutes=20,
                depends_on=["P4"],
            ),
            ProjectPhase(
                id="P6",
                name="Team Guide",
                name_uz="Jamoa qo'llanmasi",
                description="Jamoa uchun qo'llanma tayyorlash",
                role=PhaseRole.PROJECT_MANAGER,
                service_type="pm",
                estimated_minutes=15,
                depends_on=["P5"],
            ),
            # ... (design phases will be added dynamically)
        ]

    def create_checklist(
        self,
        project_id: str,
        client_name: str,
        services: List[str],
        client_id: Optional[str] = None,
        deadline: Optional[datetime] = None,
    ) -> ProjectChecklist:
        """Loyiha uchun checklist yaratish"""

        phases = []

        # Add sales phases (always included)
        phases.extend(self.phase_templates.get("hunter", []))
        phases.extend(self.phase_templates.get("setter", []))
        phases.extend(self.phase_templates.get("closer", []))

        # Add PM phases
        pm_phases = self.phase_templates.get("pm", []).copy()
        phases.extend(pm_phases)

        # Add design phases based on services
        design_phases = self._create_design_phases(services)
        phases.extend(design_phases)

        # Add final PM phases
        phases.extend(
            [
                ProjectPhase(
                    id="P10",
                    name="File Collection",
                    name_uz="Fayllarni yig'ish",
                    description="Barcha fayllarni tekshirish va yig'ish",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="pm",
                    estimated_minutes=30,
                ),
                ProjectPhase(
                    id="P11",
                    name="Final Presentation",
                    name_uz="Yakuniy prezentatsiya",
                    description="Final presentation tayyorlash",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="pm",
                    estimated_minutes=45,
                    depends_on=["P10"],
                ),
                ProjectPhase(
                    id="P12",
                    name="Client Handover",
                    name_uz="Mijozga topshirish",
                    description="Mijozga topshirish uchrashuvi",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="pm",
                    estimated_minutes=30,
                    depends_on=["P11"],
                ),
                ProjectPhase(
                    id="P13",
                    name="Brand Training",
                    name_uz="Brand trening",
                    description="Brand guidelines trening (mijoz jamoasi uchun)",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="pm",
                    estimated_minutes=60,
                    depends_on=["P12"],
                ),
                ProjectPhase(
                    id="P14",
                    name="File Upload",
                    name_uz="Fayllarni yuklash",
                    description="Barcha fayllarni yuklash (Google Drive, Dropbox)",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="pm",
                    estimated_minutes=20,
                    depends_on=["P13"],
                ),
                ProjectPhase(
                    id="P15",
                    name="Case Study",
                    name_uz="Case study",
                    description="Loyiha hisoboti va case study yozish",
                    role=PhaseRole.PROJECT_MANAGER,
                    service_type="pm",
                    estimated_minutes=45,
                    depends_on=["P14"],
                ),
            ]
        )

        # Unlock first phases (no dependencies)
        for phase in phases:
            if not phase.depends_on:
                phase.status = PhaseStatus.PENDING

        checklist = ProjectChecklist(
            project_id=project_id,
            client_name=client_name,
            client_id=client_id,
            services=services,
            phases=phases,
            deadline=deadline,
        )

        self.checklists[project_id] = checklist
        return checklist

    def _create_design_phases(self, services: List[str]) -> List[ProjectPhase]:
        """Dizayn bosqichlarini yaratish"""
        phases = []
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

        # Visual Identity
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

    def start_phase(self, project_id: str, phase_id: str, user_id: str) -> bool:
        """Bosqichni boshlash"""
        checklist = self.checklists.get(project_id)
        if not checklist:
            return False

        phase = next((p for p in checklist.phases if p.id == phase_id), None)
        if not phase:
            return False

        # Tekshirish - mumkinmi boshlash?
        completed = [
            p.id for p in checklist.phases if p.status == PhaseStatus.COMPLETED
        ]
        if not phase.can_start(completed):
            return False

        if phase.status != PhaseStatus.PENDING and phase.status != PhaseStatus.LOCKED:
            return False

        phase.status = PhaseStatus.IN_PROGRESS
        phase.started_at = datetime.now()
        return True

    def complete_phase(
        self, project_id: str, phase_id: str, user_id: str, evidence: Dict = None
    ) -> Dict[str, Any]:
        """Bosqichni yakunlash"""
        checklist = self.checklists.get(project_id)
        if not checklist:
            return {"success": False, "error": "Project not found"}

        phase = next((p for p in checklist.phases if p.id == phase_id), None)
        if not phase:
            return {"success": False, "error": "Phase not found"}

        if phase.status != PhaseStatus.IN_PROGRESS:
            return {"success": False, "error": "Phase not in progress"}

        # Yakunlash
        phase.status = PhaseStatus.COMPLETED
        phase.completed_at = datetime.now()

        if evidence:
            phase.attachments.append(
                {"timestamp": datetime.now().isoformat(), **evidence}
            )

        # Keyingi bosqichlarni ochish
        unlocked = []
        for p in checklist.phases:
            if p.status == PhaseStatus.LOCKED:
                completed_ids = [
                    cp.id
                    for cp in checklist.phases
                    if cp.status == PhaseStatus.COMPLETED
                ]
                if p.can_start(completed_ids):
                    p.status = PhaseStatus.PENDING
                    unlocked.append(p.id)

        # Loyiha tugaganmi?
        all_completed = all(p.status == PhaseStatus.COMPLETED for p in checklist.phases)
        if all_completed:
            checklist.completed_at = datetime.now()

        return {
            "success": True,
            "phase": phase.to_dict(),
            "unlocked_phases": unlocked,
            "project_completed": all_completed,
        }

    def get_checklist(self, project_id: str) -> Optional[ProjectChecklist]:
        """Checklist olish"""
        return self.checklists.get(project_id)

    def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """Loyiha xulosasi"""
        checklist = self.checklists.get(project_id)
        if not checklist:
            return {"error": "Project not found"}

        progress = checklist.get_progress()

        return {
            "project_id": checklist.project_id,
            "client_name": checklist.client_name,
            "services": checklist.services,
            "progress": progress,
            "next_phase": (
                checklist.get_next_pending().to_dict()
                if checklist.get_next_pending()
                else None
            ),
            "deadline": checklist.deadline.isoformat() if checklist.deadline else None,
            "days_remaining": (
                (checklist.deadline - datetime.now()).days
                if checklist.deadline
                else None
            ),
            "created_at": checklist.created_at.isoformat(),
            "completed_at": (
                checklist.completed_at.isoformat() if checklist.completed_at else None
            ),
        }


# Singleton
_phase_manager: Optional[ProjectPhaseManager] = None


def get_project_phase_manager() -> ProjectPhaseManager:
    """Global phase manager"""
    global _phase_manager
    if _phase_manager is None:
        _phase_manager = ProjectPhaseManager()
    return _phase_manager
