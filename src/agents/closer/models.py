"""
Data models for Autonomous Sales Closer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    """Suhbat holati"""

    user_id: str
    stage: str = "initial"
    context: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_interaction: datetime = field(default_factory=datetime.now)
    deal_value: Optional[float] = None
    objections: List[str] = field(default_factory=list)
    commitment_achieved: bool = False
    autonomy_level: str = "full"

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
        )
        self.last_interaction = datetime.now()

    def is_stale(self, hours: int = 24) -> bool:
        return datetime.now() - self.last_interaction > timedelta(hours=hours)


@dataclass
class DealProposal:
    """Taklif paketi"""

    service_type: str
    base_price: float
    scope: Dict[str, Any]
    timeline: str
    discount_pct: float = 0.0
    special_terms: List[str] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return self.base_price * (1 - self.discount_pct / 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_type": self.service_type,
            "base_price": self.base_price,
            "discount_pct": self.discount_pct,
            "final_price": self.total_value,
            "timeline": self.timeline,
            "scope": self.scope,
            "special_terms": self.special_terms,
        }
