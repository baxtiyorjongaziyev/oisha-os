"""
Data models, enums, workflow steps, and user task representations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("MandatoryWorkflow")

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
