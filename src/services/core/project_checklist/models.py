"""
Data models and helper functions for client project checklist.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ClientProjectChecklist")

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
