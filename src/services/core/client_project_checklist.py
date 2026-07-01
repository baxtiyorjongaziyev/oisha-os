"""
Client Project Checklist - Mijoz uchun to'liq end-to-end checklist
Jon.Branding - Lead topishdan loyiha topshirishgacha barcha qadamlar
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from src.services.core.service_configurator import get_service_configurator, ServiceType
from src.services.core.project_phases import get_project_phase_manager, PhaseStatus
from src.services.core.mandatory_workflow import get_mandatory_workflow


@dataclass
class ClientProject:
    """Mijoz loyihasi"""

    project_id: str
    client_name: str
    client_id: Optional[str] = None
    client_phone: Optional[str] = None
    client_telegram: Optional[str] = None

    # Xizmatlar
    services: List[str] = field(default_factory=list)
    total_price: int = 0
    total_days: int = 0

    # Timeline
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None

    # Status
    status: str = "new"  # new, in_progress, on_hold, completed, cancelled

    # AmoCRM
    amo_lead_id: Optional[int] = None
    amo_contact_id: Optional[int] = None

    # Team
    assigned_hunter: Optional[str] = None
    assigned_setter: Optional[str] = None
    assigned_closer: Optional[str] = None
    assigned_pm: Optional[str] = None
    assigned_designer: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "project_id": self.project_id,
            "client_name": self.client_name,
            "services": self.services,
            "total_price": self.total_price,
            "total_days": self.total_days,
            "status": self.status,
            "progress_percentage": 0,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "team": {
                "hunter": self.assigned_hunter,
                "setter": self.assigned_setter,
                "closer": self.assigned_closer,
                "pm": self.assigned_pm,
                "designer": self.assigned_designer,
            },
        }


class ClientProjectChecklistManager:
    """
    Mijoz loyihalari uchun to'liq checklist boshqaruvchisi

    Bu tizim quyidagilarni birlashtiradi:
    1. Service Configurator - Xizmatlarni tanlash va narx hisoblash
    2. Project Phases - Loyiha bosqichlarini yaratish
    3. Mandatory Workflow - Jamoa vazifalarini nazorat qilish

    Har bir mijoz uchun:
    - Sales pipeline (Hunter → Setter → Closer)
    - Loyiha bosqichlari (PM → Designer)
    - Real-time tracking
    - Avtomatik xabarnomalar
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

    def create_project(
        self,
        client_name: str,
        selected_services: List[ServiceType],
        client_id: Optional[str] = None,
        client_phone: Optional[str] = None,
        client_telegram: Optional[str] = None,
        start_date: Optional[datetime] = None,
        assigned_team: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Yangi loyiha yaratish

        Args:
            client_name: Mijoz ismi
            selected_services: Tanlangan xizmatlar
            client_id: Mijoz ID (Telegram yoki boshqa)
            client_phone: Telefon raqami
            client_telegram: Telegram ID
            start_date: Boshlanish sanasi
            assigned_team: Jamoa a'zolari IDs {hunter, setter, closer, pm, designer}

        Returns:
            Project summary with checklist
        """

        # 1. Xizmatlarni konfiguratsiya qilish
        config = self.service_config.configure_project(
            client_name=client_name, selected_services=selected_services
        )

        project_id = config["project_id"]

        # 2. Loyiha yaratish
        project = ClientProject(
            project_id=project_id,
            client_name=client_name,
            client_id=client_id,
            client_phone=client_phone,
            client_telegram=client_telegram,
            services=config["service_types"],
            total_price=config["total_price"],
            total_days=config["total_days"],
            start_date=start_date or datetime.now(),
            deadline=(start_date or datetime.now())
            + timedelta(days=config["total_days"]),
        )

        # Jamoa tayinlash
        if assigned_team:
            project.assigned_hunter = assigned_team.get("hunter")
            project.assigned_setter = assigned_team.get("setter")
            project.assigned_closer = assigned_team.get("closer")
            project.assigned_pm = assigned_team.get("pm")
            project.assigned_designer = assigned_team.get("designer")

        self.projects[project_id] = project

        # 3. Checklist yaratish
        checklist = self.phase_manager.create_checklist(
            project_id=project_id,
            client_name=client_name,
            services=config["service_types"],
            client_id=client_id,
            deadline=project.deadline,
        )

        # 4. Hunter vazifalarini yaratish
        if project.assigned_hunter:
            self.workflow.assign_daily_tasks(
                user_id=project.assigned_hunter,
                user_name="Hunter",
                role=self.workflow.workflows,  # Will use from mandatory_workflow
            )

        return {
            "project_id": project_id,
            "client_name": client_name,
            "services": config["services"],
            "total_price": config["total_price"],
            "total_days": config["total_days"],
            "total_phases": len(checklist.phases),
            "discount_applied": config["discount_applied"],
            "deadline": project.deadline.isoformat(),
            "checklist_url": f"/checklist/{project_id}",
            "message": (
                f"✅ Loyiha yaratildi: {project_id}\n"
                f"📋 {len(checklist.phases)} ta qadam\n"
                f"💰 ${config['total_price']}\n"
                f"⏰ {config['total_days']} kun"
            ),
        }

    def get_project_checklist(self, project_id: str) -> Optional[Dict]:
        """Loyiha checklistini olish"""
        project = self.projects.get(project_id)
        if not project:
            return None

        checklist = self.phase_manager.get_checklist(project_id)
        if not checklist:
            return None

        # Group phases by role and service
        by_role = {}
        by_service = {}

        for phase in checklist.phases:
            # By role
            role = phase.role.value
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(phase.to_dict())

            # By service
            service = phase.service_type
            if service not in by_service:
                by_service[service] = []
            by_service[service].append(phase.to_dict())

        progress = checklist.get_progress()
        next_phase = checklist.get_next_pending()

        return {
            "project_id": project_id,
            "client_name": project.client_name,
            "services": project.services,
            "status": project.status,
            "progress": progress,
            "next_phase": next_phase.to_dict() if next_phase else None,
            "deadline": project.deadline.isoformat() if project.deadline else None,
            "phases_by_role": by_role,
            "phases_by_service": by_service,
            "all_phases": [p.to_dict() for p in checklist.phases],
        }

    def start_phase(
        self, project_id: str, phase_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Bosqichni boshlash"""

        success = self.phase_manager.start_phase(project_id, phase_id, user_id)

        if not success:
            return {
                "success": False,
                "error": "Bosqichni boshlash mumkin emas. Oldingi bosqich bajarilmagan.",
            }

        checklist = self.phase_manager.get_checklist(project_id)
        phase = next((p for p in checklist.phases if p.id == phase_id), None)

        return {
            "success": True,
            "phase_id": phase_id,
            "phase_name": phase.name_uz if phase else "",
            "status": "in_progress",
            "message": f"🚀 '{phase.name_uz if phase else phase_id}' boshlandi!",
        }

    def complete_phase(
        self,
        project_id: str,
        phase_id: str,
        user_id: str,
        evidence: Dict = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Bosqichni yakunlash"""

        result = self.phase_manager.complete_phase(
            project_id=project_id, phase_id=phase_id, user_id=user_id, evidence=evidence
        )

        if not result["success"]:
            return result

        # Check if project completed
        if result.get("project_completed"):
            project = self.projects.get(project_id)
            if project:
                project.status = "completed"

                # Notify handlers
                for handler in self.on_project_complete:
                    asyncio.create_task(handler(project))

        # Get next phase info
        checklist = self.phase_manager.get_checklist(project_id)
        next_phase = checklist.get_next_pending()

        return {
            "success": True,
            "phase_id": phase_id,
            "unlocked_phases": result.get("unlocked_phases", []),
            "next_phase": (
                {
                    "id": next_phase.id,
                    "name": next_phase.name_uz,
                    "role": next_phase.role.value,
                }
                if next_phase
                else None
            ),
            "project_completed": result.get("project_completed", False),
            "message": (
                f"✅ Bosqich yakunlandi!\n"
                f"🔓 {len(result.get('unlocked_phases', []))} ta yangi qadam ochildi.\n"
                f"➡️ Keyingisi: {next_phase.name_uz if next_phase else 'Yoq'}"
            ),
        }

    def get_user_tasks(self, user_id: str, role: str) -> List[Dict]:
        """Foydalanuvchi vazifalarini olish"""

        tasks = []

        for project_id, project in self.projects.items():
            checklist = self.phase_manager.get_checklist(project_id)
            if not checklist:
                continue

            # Get phases for this role
            role_phases = [
                p
                for p in checklist.phases
                if p.role.value == role
                and p.status in [PhaseStatus.PENDING, PhaseStatus.IN_PROGRESS]
            ]

            for phase in role_phases:
                tasks.append(
                    {
                        "project_id": project_id,
                        "client_name": project.client_name,
                        "phase_id": phase.id,
                        "phase_name": phase.name_uz,
                        "service": phase.service_type,
                        "status": phase.status.value,
                        "estimated_minutes": phase.estimated_minutes,
                        "deadline": (
                            checklist.deadline.isoformat()
                            if checklist.deadline
                            else None
                        ),
                    }
                )

        return tasks

    def get_dashboard(self) -> Dict[str, Any]:
        """Umumiy dashboard"""

        total_projects = len(self.projects)
        active_projects = len(
            [p for p in self.projects.values() if p.status == "in_progress"]
        )
        completed_projects = len(
            [p for p in self.projects.values() if p.status == "completed"]
        )

        total_value = sum(p.total_price for p in self.projects.values())

        # Projects by status
        by_status = {}
        for p in self.projects.values():
            by_status[p.status] = by_status.get(p.status, 0) + 1

        # Active phases count
        active_phases = 0
        pending_phases = 0
        completed_phases = 0

        for project_id in self.projects:
            checklist = self.phase_manager.get_checklist(project_id)
            if checklist:
                progress = checklist.get_progress()
                active_phases += progress["in_progress"]
                pending_phases += progress["pending"] + progress["locked"]
                completed_phases += progress["completed"]

        return {
            "total_projects": total_projects,
            "active_projects": active_projects,
            "completed_projects": completed_projects,
            "total_value": total_value,
            "by_status": by_status,
            "phases": {
                "active": active_phases,
                "pending": pending_phases,
                "completed": completed_phases,
            },
            "recent_projects": [
                {
                    "id": p.project_id,
                    "client": p.client_name,
                    "status": p.status,
                    "price": p.total_price,
                }
                for p in sorted(
                    self.projects.values(), key=lambda x: x.created_at, reverse=True
                )[:5]
            ],
        }

    def generate_daily_report(self) -> str:
        """Kunlik hisobot"""
        dashboard = self.get_dashboard()

        lines = [
            "📊 JON.BRANDING - KUNLIK HISOBOT",
            f"Sana: {datetime.now().strftime('%Y-%m-%d')}",
            "=" * 50,
            "",
            f"📁 Loyihalar: {dashboard['total_projects']} ta",
            f"   • Faol: {dashboard['active_projects']}",
            f"   • Yakunlangan: {dashboard['completed_projects']}",
            f"   • Umumiy qiymat: ${dashboard['total_value']:,}",
            "",
            "📋 Bosqichlar:",
            f"   • Bajarilmoqda: {dashboard['phases']['active']}",
            f"   • Kutilmoqda: {dashboard['phases']['pending']}",
            f"   • Yakunlangan: {dashboard['phases']['completed']}",
            "",
            "🆕 So'nggi loyihalar:",
        ]

        for proj in dashboard["recent_projects"]:
            emoji = {"in_progress": "🟡", "completed": "✅", "new": "🆕"}.get(
                proj["status"], "⚪"
            )
            lines.append(f"   {emoji} {proj['client']}: ${proj['price']}")

        return "\n".join(lines)


# Singleton
_checklist_manager: Optional[ClientProjectChecklistManager] = None


def get_client_project_manager() -> ClientProjectChecklistManager:
    """Global manager instance"""
    global _checklist_manager
    if _checklist_manager is None:
        _checklist_manager = ClientProjectChecklistManager()
    return _checklist_manager


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
