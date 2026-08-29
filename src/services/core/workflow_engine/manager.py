"""
MandatoryWorkflowManager main orchestrator and singleton factory.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.context import app_ctx
from src.services.core.workflow_engine.models import (
    Role,
    TaskStatus,
    UserTask,
    WorkflowStep,
)
from src.services.core.workflow_engine.templates import WorkflowTemplatesMixin

logger = logging.getLogger("MandatoryWorkflow")


class MandatoryWorkflowManager(WorkflowTemplatesMixin):
    """
    Jon Branding uchun majburiy ketma-ketlik va intizom boshqaruvchisi.
    """

    def __init__(self):
        self.workflows: Dict[str, List[WorkflowStep]] = {}
        self.active_tasks: Dict[str, UserTask] = {}
        self.completed_tasks: List[UserTask] = []
        self.blocked_users: Dict[str, str] = {}  # user_id -> reason

        # Jon.Branding uchun standart workflow
        self._setup_jon_branding_workflows()

        # Event handlers
        self.on_step_complete: List[Callable] = []
        self.on_step_blocked: List[Callable] = []
        self.on_daily_check: List[Callable] = []

    def assign_daily_tasks(
        self, user_id: str, user_name: str, role: Role, workflow_type: str = None
    ) -> List[UserTask]:
        """Kunlik vazifalarni taqsimlash"""

        # Agar foydalanuvchi bloklangan bo'lsa
        if user_id in self.blocked_users:
            return []

        # Workflow tanlash
        if not workflow_type:
            workflow_map = {
                Role.HUNTER: "hunter_daily",
                Role.SETTER: "setter_daily",
                Role.CLOSER: "closer_meeting",
                Role.PROJECT_MANAGER: "pm_daily",
                Role.DESIGNER: "designer_task",
            }
            workflow_type = workflow_map.get(role)

        if not workflow_type or workflow_type not in self.workflows:
            return []

        workflow = self.workflows[workflow_type]
        tasks = []

        for step in workflow:
            # Check if blocked by previous step
            is_blocked = False
            blocked_reason = None

            if step.blocked_until:
                # Check if prerequisite is completed
                prereq_task = self._find_task(user_id, step.blocked_until)
                if not prereq_task or prereq_task.status != TaskStatus.COMPLETED:
                    is_blocked = True
                    blocked_reason = f"{step.blocked_until} qadami bajarilishi kerak"

            task = UserTask(
                id=f"{user_id}_{step.id}_{datetime.now().strftime('%Y%m%d')}",
                user_id=user_id,
                user_name=user_name,
                role=role,
                step=step,
                status=TaskStatus.BLOCKED if is_blocked else TaskStatus.MANDATORY,
                deadline=datetime.now() + timedelta(hours=step.estimated_time / 60 + 2),
            )

            if is_blocked:
                task.block(blocked_reason, "system")

            self.active_tasks[task.id] = task
            tasks.append(task)

        return tasks

    def start_task(self, task_id: str, user_id: str) -> bool:
        """Vazifani boshlash"""
        task = self.active_tasks.get(task_id)

        if not task:
            return False

        if task.user_id != user_id:
            return False  # Boshqa foydalanuvchining vazifasi

        if task.status == TaskStatus.BLOCKED:
            return False  # Bloklangan

        return task.start()

    def complete_task(
        self, task_id: str, user_id: str, evidence: Dict = None
    ) -> Dict[str, Any]:
        """Vazifani yakunlash va keyingisini ochish"""

        task = self.active_tasks.get(task_id)

        if not task or task.user_id != user_id:
            return {"success": False, "error": "Task not found or unauthorized"}

        if task.status != TaskStatus.IN_PROGRESS:
            return {"success": False, "error": "Task not in progress"}

        # Complete current task
        task.complete(evidence)

        # Move to completed
        self.completed_tasks.append(task)
        del self.active_tasks[task_id]

        # Unblock next tasks
        unblocked = self._unblock_next_tasks(user_id, task.step.id)

        # Trigger handlers
        for handler in self.on_step_complete:
            asyncio.create_task(handler(task))

        return {
            "success": True,
            "task": task.to_dict() if hasattr(task, "to_dict") else str(task),
            "unblocked_tasks": unblocked,
            "next_step": self._get_next_step(user_id, task.step),
        }

    def _unblock_next_tasks(self, user_id: str, completed_step_id: str) -> List[str]:
        """Keyingi vazifalarni ochish"""
        unblocked = []

        for task_id, task in self.active_tasks.items():
            if task.user_id == user_id and task.status == TaskStatus.BLOCKED:
                if task.step.blocked_until == completed_step_id:
                    task.status = TaskStatus.MANDATORY
                    task.blocked_reason = None
                    task.blocked_by = None
                    unblocked.append(task_id)

        return unblocked

    def _get_next_step(
        self, user_id: str, current_step: WorkflowStep
    ) -> Optional[Dict]:
        """Keyingi qadamni olish"""
        for task_id, task in self.active_tasks.items():
            if task.user_id == user_id and task.step.order == current_step.order + 1:
                return {
                    "id": task.step.id,
                    "name": task.step.name,
                    "status": task.status.value,
                }
        return None

    def _find_task(self, user_id: str, step_id: str) -> Optional[UserTask]:
        """Vazifa qidirish"""
        for task in self.completed_tasks:
            if task.user_id == user_id and task.step.id == step_id:
                return task
        return None

    def block_user(self, user_id: str, reason: str):
        """Foydalanuvchini bloklash (qoidani buzganda)"""
        self.blocked_users[user_id] = reason

        # Block all active tasks
        for task_id, task in self.active_tasks.items():
            if task.user_id == user_id:
                task.block(reason, "admin")

    def get_user_status(self, user_id: str) -> Dict[str, Any]:
        """Foydalanuvchi statusi"""

        active = [t for t in self.active_tasks.values() if t.user_id == user_id]
        completed_today = [
            t
            for t in self.completed_tasks
            if t.user_id == user_id
            and t.completed_at
            and t.completed_at.date() == datetime.now().date()
        ]

        return {
            "user_id": user_id,
            "is_blocked": user_id in self.blocked_users,
            "block_reason": self.blocked_users.get(user_id),
            "active_tasks": len(active),
            "completed_today": len(completed_today),
            "mandatory_pending": len(
                [t for t in active if t.status == TaskStatus.MANDATORY]
            ),
            "blocked_tasks": len([t for t in active if t.status == TaskStatus.BLOCKED]),
            "next_mandatory": self._get_next_mandatory(user_id),
        }

    def _get_next_mandatory(self, user_id: str) -> Optional[Dict]:
        """Keyingi majburiy vazifa"""
        for task in self.active_tasks.values():
            if task.user_id == user_id and task.status == TaskStatus.MANDATORY:
                return {
                    "id": task.step.id,
                    "name": task.step.name,
                    "description": task.step.description,
                    "estimated_minutes": task.step.estimated_time,
                }
        return None

    def get_daily_report(self) -> Dict[str, Any]:
        """Kunlik umumiy hisobot"""
        today = datetime.now().date()

        completed_today = [
            t
            for t in self.completed_tasks
            if t.completed_at and t.completed_at.date() == today
        ]

        overdue = [t for t in self.active_tasks.values() if t.is_overdue()]

        by_role = {}
        for task in completed_today:
            role = task.role.value
            if role not in by_role:
                by_role[role] = 0
            by_role[role] += 1

        return {
            "date": today.isoformat(),
            "completed_tasks": len(completed_today),
            "overdue_tasks": len(overdue),
            "blocked_users": len(self.blocked_users),
            "active_users": len(set(t.user_id for t in self.active_tasks.values())),
            "by_role": by_role,
            "top_performers": self._get_top_performers(today),
            "violations": self._get_violations(today),
        }

    def _get_top_performers(self, date) -> List[Dict]:
        """Eng yaxshi bajaruvchilar"""
        user_scores = {}

        for task in self.completed_tasks:
            if task.completed_at and task.completed_at.date() == date:
                uid = task.user_id
                if uid not in user_scores:
                    user_scores[uid] = {"name": task.user_name, "count": 0}
                user_scores[uid]["count"] += 1

        sorted_users = sorted(
            user_scores.items(), key=lambda x: x[1]["count"], reverse=True
        )
        return [{"user_id": uid, **data} for uid, data in sorted_users[:5]]

    def _get_violations(self, date) -> List[Dict]:
        """Qoida buzilishlari"""
        # Track users who didn't complete mandatory tasks
        violations = []

        for user_id, reason in self.blocked_users.items():
            violations.append(
                {
                    "user_id": user_id,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return violations


_workflow_instance: Optional[MandatoryWorkflowManager] = None


def get_mandatory_workflow() -> MandatoryWorkflowManager:
    """Global workflow manager instance"""
    global _workflow_instance
    if getattr(app_ctx, "mandatory_workflow", None) is not None:
        return app_ctx.mandatory_workflow
    if _workflow_instance is None:
        _workflow_instance = MandatoryWorkflowManager()
        app_ctx.mandatory_workflow = _workflow_instance
    return _workflow_instance

