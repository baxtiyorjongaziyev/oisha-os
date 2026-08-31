"""
Data models and enumerations for Deal Lifecycle management.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class DealStage(Enum):
    """Bitim bosqichlari"""

    NEW = "new_lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal_sent"
    NEGOTIATION = "negotiation"
    COMMITMENT = "commitment"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    NO_RESPONSE = "no_response"
    LEAD = "new_lead"
    DISCOVERY = "qualified"
    WON = "closed_won"
    LOST = "closed_lost"


class DealPriority(Enum):
    """Prioritet darajalari"""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    LOW = "cold"
    MEDIUM = "warm"
    HIGH = "hot"
    CRITICAL = "hot"


@dataclass
class Deal:
    """Bitim obyekti"""

    id: str
    user_id: str
    stage: DealStage = DealStage.NEW
    priority: DealPriority = DealPriority.WARM
    value: Optional[float] = None
    service_type: str = ""
    source: str = ""

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    next_action_due: Optional[datetime] = None

    history: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    crm_lead_id: Optional[str] = None
    crm_contact_id: Optional[str] = None

    client_name: str = ""
    phone: str = ""
    company: str = ""
    budget: Optional[float] = None
    timeline: str = ""
    contract_draft: Optional[str] = None
    risk_level: str = "low"
    channel: str = "telegram"

    @property
    def deal_id(self) -> str:
        return self.id

    def update_stage(self, new_stage: DealStage, reason: str = ""):
        old_stage = self.stage
        self.stage = new_stage
        self.updated_at = datetime.now()
        self.history.append(
            {
                "from_stage": old_stage.value,
                "to_stage": new_stage.value,
                "timestamp": self.updated_at.isoformat(),
                "reason": reason,
            }
        )
        self._update_next_action()

    def _update_next_action(self):
        intervals = {
            DealPriority.HOT: timedelta(hours=24),
            DealPriority.WARM: timedelta(hours=72),
            DealPriority.COLD: timedelta(days=7),
        }
        self.next_action_due = datetime.now() + intervals.get(self.priority, timedelta(hours=48))

    def is_overdue(self) -> bool:
        if not self.next_action_due:
            return False
        return datetime.now() > self.next_action_due

    def days_in_stage(self) -> int:
        return (datetime.now() - self.updated_at).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stage": self.stage.value,
            "priority": self.priority.value,
            "value": self.value or self.budget,
            "service_type": self.service_type,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "next_action_due": self.next_action_due.isoformat() if self.next_action_due else None,
            "history_count": len(self.history),
            "days_in_stage": self.days_in_stage(),
            "is_overdue": self.is_overdue(),
            "client_name": self.client_name,
        }
