"""
Task filtering, agency dashboard collation, and daily reporting operations mixin.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from src.services.core.project_phases import PhaseStatus

logger = logging.getLogger("ClientProjectChecklist")


class ReportingOperationsMixin:
    """Provides user-specific task lists, aggregated metrics, and health reports."""

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
