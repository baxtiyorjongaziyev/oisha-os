"""
Data models, enums, and checklist containers for Project Phases.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
