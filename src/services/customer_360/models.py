"""
Customer 360 Data Models.

Represents a unified profile of a client aggregating data from:
- AmoCRM (leads, deals, stages, managers, tags)
- Telephony / Voice (Call STT transcript, scoring, conversion advice, agreed dates)
- Telegram (chat history, agreements)
- Airtable (project delivery phases, payments, outstanding debt)
- Instagram (comments, direct messages, outreach)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class CallInteraction:
    """Record of a phone call interaction with AI analysis."""
    call_id: str
    timestamp: str
    duration_seconds: int
    caller_phone: str
    manager_name: str
    category: str
    summary: str
    client_mood: str
    client_talk_pct: int = 50
    manager_talk_pct: int = 50
    seller_score: Optional[int] = None  # 1-10
    client_score: Optional[int] = None  # 1-10
    agreed_datetime: Optional[str] = None
    conversion_advice: Optional[str] = None
    transcript: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "caller_phone": self.caller_phone,
            "manager_name": self.manager_name,
            "category": self.category,
            "summary": self.summary,
            "client_mood": self.client_mood,
            "client_talk_pct": self.client_talk_pct,
            "manager_talk_pct": self.manager_talk_pct,
            "seller_score": self.seller_score,
            "client_score": self.client_score,
            "agreed_datetime": self.agreed_datetime,
            "conversion_advice": self.conversion_advice,
            "transcript": self.transcript,
        }


@dataclass
class Customer360Profile:
    """Unified 360-degree customer profile."""
    name: str
    phone: str = ""
    telegram_username: str = ""
    instagram_handle: str = ""
    amocrm_lead_id: Optional[int] = None
    amocrm_lead_name: str = ""
    amocrm_pipeline: str = ""
    amocrm_status: str = ""
    amocrm_budget: int = 0
    responsible_manager: str = ""
    tags: List[str] = field(default_factory=list)
    airtable_project_name: str = ""
    airtable_phase: str = ""
    airtable_paid: float = 0.0
    airtable_debt: float = 0.0
    airtable_deadline: str = ""
    calls: List[CallInteraction] = field(default_factory=list)
    telegram_messages: List[str] = field(default_factory=list)
    telegram_group_id: Optional[int] = None
    telegram_group_title: str = ""
    telegram_group_link: str = ""
    telegram_group_messages: List[str] = field(default_factory=list)
    instagram_interactions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    updated_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "phone": self.phone,
            "telegram_username": self.telegram_username,
            "instagram_handle": self.instagram_handle,
            "amocrm_lead_id": self.amocrm_lead_id,
            "amocrm_lead_name": self.amocrm_lead_name,
            "amocrm_pipeline": self.amocrm_pipeline,
            "amocrm_status": self.amocrm_status,
            "amocrm_budget": self.amocrm_budget,
            "responsible_manager": self.responsible_manager,
            "tags": self.tags,
            "airtable_project_name": self.airtable_project_name,
            "airtable_phase": self.airtable_phase,
            "airtable_paid": self.airtable_paid,
            "airtable_debt": self.airtable_debt,
            "airtable_deadline": self.airtable_deadline,
            "calls": [c.to_dict() for c in self.calls],
            "telegram_messages": self.telegram_messages,
            "telegram_group_id": self.telegram_group_id,
            "telegram_group_title": self.telegram_group_title,
            "telegram_group_link": self.telegram_group_link,
            "telegram_group_messages": self.telegram_group_messages,
            "instagram_interactions": self.instagram_interactions,
            "notes": self.notes,
            "updated_at": self.updated_at,
        }
