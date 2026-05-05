"""
Mandatory Workflow System - Oisha-OS
Jon.Branding Agency - Strict Process Enforcement
Har bir a'zo, har bir qadam majburiy!
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import json


class Role(Enum):
    """Jon.Branding rollari"""

    HUNTER = "hunter"  # Lead ovlash
    SETTER = "setter"  # Uchrashuv belgilash
    CLOSER = "closer"  # Bitimni yopish
    FARMER = "farmer"  # Mijozni saqlash
    PROJECT_MANAGER = "pm"  # Loyiha boshqaruvchi
    DESIGNER = "designer"  # Dizayner
    DEVELOPER = "developer"  # Dasturchi
    COPYWRITER = "copywriter"  # Matn yozuvchi
    DIRECTOR = "director"  # Direktor


class TaskStatus(Enum):
    """Vazifa statuslari"""

    PENDING = "pending"  # Kutilmoqda
    IN_PROGRESS = "in_progress"  # Bajarilmoqda
    COMPLETED = "completed"  # Bajarildi
    BLOCKED = "blocked"  # Bloklangan
    OVERDUE = "overdue"  # Muddati o'tdi
    MANDATORY = "mandatory"  # Majburiy - bajarilmaguncha o'tib bo'lmaydi


@dataclass
class WorkflowStep:
    """Ish jarayoni qadami"""

    id: str
    name: str
    description: str
    role: Role
    order: int

    # Majburiy qoidalar
    is_mandatory: bool = True
    estimated_time: int = 30  # daqiqa

    # Blokirovka
    blocked_until: Optional[str] = None  # Qaysi step bajarilishi kerak
    auto_block_next: bool = True  # Keyingi step avtomatik bloklanadimi?

    # Tekshirish
    requires_approval: bool = False
    approver_role: Optional[Role] = None

    # AmoCRM integration
    crm_stage_id: Optional[int] = None
    crm_pipeline_id: Optional[str] = None

    # Sub-tasks
    sub_tasks: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "role": self.role.value,
            "order": self.order,
            "is_mandatory": self.is_mandatory,
            "estimated_time": self.estimated_time,
            "blocked_until": self.blocked_until,
            "requires_approval": self.requires_approval,
        }


@dataclass
class UserTask:
    """Foydalanuvchi vazifasi"""

    id: str
    user_id: str
    user_name: str
    role: Role
    step: WorkflowStep

    status: TaskStatus = TaskStatus.MANDATORY
    assigned_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None

    # Evidence (isbot)
    evidence: List[Dict] = field(default_factory=list)
    notes: str = ""

    # Blocking
    blocked_reason: Optional[str] = None
    blocked_by: Optional[str] = None

    def start(self):
        """Vazifani boshlash"""
        if self.status == TaskStatus.MANDATORY or self.status == TaskStatus.PENDING:
            self.status = TaskStatus.IN_PROGRESS
            self.started_at = datetime.now()
            return True
        return False

    def complete(self, evidence_data: Dict = None):
        """Vazifani yakunlash"""
        if self.status == TaskStatus.IN_PROGRESS:
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now()
            if evidence_data:
                self.evidence.append(
                    {"timestamp": datetime.now().isoformat(), "data": evidence_data}
                )
            return True
        return False

    def block(self, reason: str, blocked_by: str):
        """Vazifani bloklash"""
        self.status = TaskStatus.BLOCKED
        self.blocked_reason = reason
        self.blocked_by = blocked_by

    def is_overdue(self) -> bool:
        """Muddati o'tganmi"""
        if not self.deadline:
            return False
        return datetime.now() > self.deadline

    def get_duration(self) -> Optional[int]:
        """Davomiylik (daqiqa)"""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return int((end - self.started_at).total_seconds() / 60)


class MandatoryWorkflowManager:
    """
    Majburiy ish jarayonlari boshqaruvchisi

    Har bir a'zo faqat o'zining qat'iy belgilangan
    qadamlarini bajarishiga ruxsat etiladi.
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

    def _setup_jon_branding_workflows(self):
        """Jon.Branding uchun qat'iy ish jarayonlari"""

        # HUNTER workflow - Lead ovlash
        self.workflows["hunter_daily"] = [
            WorkflowStep(
                id="h_1",
                name="Kunlik rejani olish",
                description="Direktordan kunlik Surgical Mission olish",
                role=Role.HUNTER,
                order=1,
                estimated_time=15,
                crm_pipeline_id="hunter",
            ),
            WorkflowStep(
                id="h_2",
                name="Lead qidirish",
                description="50 ta yangi lead topish (Telegram, LinkedIn, Instagram)",
                role=Role.HUNTER,
                order=2,
                estimated_time=120,
                blocked_until="h_1",
            ),
            WorkflowStep(
                id="h_3",
                name="Birinchi kontakt",
                description="20 ta lead bilan aloqa qilish (cold outreach)",
                role=Role.HUNTER,
                order=3,
                estimated_time=90,
                blocked_until="h_2",
            ),
            WorkflowStep(
                id="h_4",
                name="CRM'ga yuklash",
                description="Barcha leadlarni AmoCRM'ga kiritish",
                role=Role.HUNTER,
                order=4,
                estimated_time=30,
                blocked_until="h_3",
                crm_stage_id=53729371,
            ),
            WorkflowStep(
                id="h_5",
                name="Kunlik hisobot",
                description="Direktorga natijalar haqida hisobot",
                role=Role.HUNTER,
                order=5,
                estimated_time=15,
                blocked_until="h_4",
                requires_approval=True,
                approver_role=Role.DIRECTOR,
            ),
        ]

        # SETTER workflow - Uchrashuv belgilash
        self.workflows["setter_daily"] = [
            WorkflowStep(
                id="s_1",
                name="Kvalifikatsiya tekshirish",
                description="CRM'dagi leadlarni saralash (qualified vs unqualified)",
                role=Role.SETTER,
                order=1,
                estimated_time=30,
                crm_pipeline_id="setter",
            ),
            WorkflowStep(
                id="s_2",
                name="Qo'ng'iroq qilish",
                description="15 ta qualified leadga qo'ng'iroq qilish",
                role=Role.SETTER,
                order=2,
                estimated_time=90,
                blocked_until="s_1",
            ),
            WorkflowStep(
                id="s_3",
                name="Uchrashuv belgilash",
                description="Kamida 3 ta uchrashuv (strategy session) belgilash",
                role=Role.SETTER,
                order=3,
                estimated_time=60,
                blocked_until="s_2",
                crm_stage_id=142,
            ),
            WorkflowStep(
                id="s_4",
                name="Kalendar tasdiqlash",
                description="Uchrashuvlarni kalendar'ga qo'shish va tasdiqlash",
                role=Role.SETTER,
                order=4,
                estimated_time=15,
                blocked_until="s_3",
            ),
            WorkflowStep(
                id="s_5",
                name="Eslatma yuborish",
                description="Mijozlarga uchrashuv eslatmasi yuborish",
                role=Role.SETTER,
                order=5,
                estimated_time=15,
                blocked_until="s_4",
                crm_stage_id=143,
            ),
        ]

        # CLOSER workflow - Bitim yopish
        self.workflows["closer_meeting"] = [
            WorkflowStep(
                id="c_1",
                name="Tayyorgarlik",
                description="Mijoz haqida research qilish (sayti, ijtimoiy tarmoqlari)",
                role=Role.CLOSER,
                order=1,
                estimated_time=30,
            ),
            WorkflowStep(
                id="c_2",
                name="Portfolio tayyorlash",
                description="Mos portfolio cases'ni tanlash",
                role=Role.CLOSER,
                order=2,
                estimated_time=20,
                blocked_until="c_1",
            ),
            WorkflowStep(
                id="c_3",
                name="Strategy Session",
                description="Uchrashuv o'tkazish (60 daqiqa)",
                role=Role.CLOSER,
                order=3,
                estimated_time=60,
                blocked_until="c_2",
                crm_stage_id=53729384,
            ),
            WorkflowStep(
                id="c_4",
                name="Taklif yuborish",
                description="Kommersiya taklifi (proposal) yuborish",
                role=Role.CLOSER,
                order=4,
                estimated_time=45,
                blocked_until="c_3",
                crm_stage_id=53729385,
            ),
            WorkflowStep(
                id="c_5",
                name="Follow-up",
                description="24 soat ichida follow-up qilish",
                role=Role.CLOSER,
                order=5,
                estimated_time=15,
                blocked_until="c_4",
                crm_stage_id=53729386,
            ),
            WorkflowStep(
                id="c_6",
                name="Bitim yopish",
                description="Shartnoma imzolash va avans olish",
                role=Role.CLOSER,
                order=6,
                estimated_time=30,
                blocked_until="c_5",
                crm_stage_id=53729390,
                requires_approval=True,
                approver_role=Role.DIRECTOR,
            ),
        ]

        # PROJECT MANAGER workflow
        self.workflows["pm_daily"] = [
            WorkflowStep(
                id="pm_1",
                name="Kunlik stand-up",
                description="Jamoa bilan qisqa stand-up (15 daqiqa)",
                role=Role.PROJECT_MANAGER,
                order=1,
                estimated_time=15,
            ),
            WorkflowStep(
                id="pm_2",
                name="Tasklarni tekshirish",
                description="Barcha loyiha tasklarini ko'rib chiqish",
                role=Role.PROJECT_MANAGER,
                order=2,
                estimated_time=30,
                blocked_until="pm_1",
            ),
            WorkflowStep(
                id="pm_3",
                name="Mijoz bilan aloqa",
                description="Aktiv loyiha mijozlari bilan status update",
                role=Role.PROJECT_MANAGER,
                order=3,
                estimated_time=45,
                blocked_until="pm_2",
            ),
            WorkflowStep(
                id="pm_4",
                name="Jadval yangilash",
                description="Timeline va deadline'larni yangilash",
                role=Role.PROJECT_MANAGER,
                order=4,
                estimated_time=20,
                blocked_until="pm_3",
            ),
            WorkflowStep(
                id="pm_5",
                name="Hisobot",
                description="Direktorga loyiha statusi hisobot",
                role=Role.PROJECT_MANAGER,
                order=5,
                estimated_time=15,
                blocked_until="pm_4",
            ),
        ]

        # DESIGNER workflow
        self.workflows["designer_task"] = [
            WorkflowStep(
                id="d_1",
                name="Brief olish",
                description="PM'dan dizayn briefini olish va tushunish",
                role=Role.DESIGNER,
                order=1,
                estimated_time=20,
            ),
            WorkflowStep(
                id="d_2",
                name="Research",
                description="Mijoz sohasi va raqobatchilarni tadqiq qilish",
                role=Role.DESIGNER,
                order=2,
                estimated_time=60,
                blocked_until="d_1",
            ),
            WorkflowStep(
                id="d_3",
                name="Moodboard",
                description="3 ta turli konsepsiya uchun moodboard",
                role=Role.DESIGNER,
                order=3,
                estimated_time=90,
                blocked_until="d_2",
            ),
            WorkflowStep(
                id="d_4",
                name="Konsepsiya",
                description="3 ta turli dizayn konsepsiyasi",
                role=Role.DESIGNER,
                order=4,
                estimated_time=240,
                blocked_until="d_3",
            ),
            WorkflowStep(
                id="d_5",
                name="Tasdiqlash",
                description="Mijoz va PM'dan tasdiqlash olish",
                role=Role.DESIGNER,
                order=5,
                estimated_time=30,
                blocked_until="d_4",
                requires_approval=True,
                approver_role=Role.PROJECT_MANAGER,
            ),
            WorkflowStep(
                id="d_6",
                name="Finalization",
                description="Yakuniy dizayn tayyorlash",
                role=Role.DESIGNER,
                order=6,
                estimated_time=180,
                blocked_until="d_5",
            ),
            WorkflowStep(
                id="d_7",
                name="Handoff",
                description="Dasturchiga yoki mijozga topshirish",
                role=Role.DESIGNER,
                order=7,
                estimated_time=30,
                blocked_until="d_6",
            ),
        ]

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


# Singleton instance
_workflow_manager: Optional[MandatoryWorkflowManager] = None


def get_mandatory_workflow() -> MandatoryWorkflowManager:
    """Global workflow manager"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = MandatoryWorkflowManager()
    return _workflow_manager
