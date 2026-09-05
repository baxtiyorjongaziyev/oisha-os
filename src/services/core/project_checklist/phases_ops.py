"""
Project creation, checklist query, and phase completion operations mixin.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.core.project_checklist.models import ClientProject, ServiceType

logger = logging.getLogger("ClientProjectChecklist")


class PhaseOperationsMixin:
    """Handles project lifecycle phases, step transitions, and validation."""

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
