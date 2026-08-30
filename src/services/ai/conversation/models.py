"""
Data models for Conversation Analysis Engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class CallRecord:
    """Qo'ng'iroq yozuvi ma'lumotlari."""

    call_id: str
    lead_id: int
    manager_id: int
    manager_name: str
    started_at: datetime
    duration_seconds: int
    audio_url: Optional[str] = None
    transcript: str = ""
    notes: str = ""

    # AmoCRM dan
    lead_name: str = ""
    lead_status: str = ""


@dataclass
class DashboardMetrics:
    """Dashboard uchun metrikalar."""

    # Umumiy
    total_calls_today: int = 0
    total_calls_week: int = 0
    avg_score_today: float = 0.0
    avg_score_week: float = 0.0

    # Natijalar
    sales_count: int = 0
    followup_count: int = 0
    lost_count: int = 0
    conversion_rate: float = 0.0

    # Faollik
    active_managers: int = 0
    total_talk_time: int = 0  # Daqiqa

    # E'tirozlar
    top_objections: List[Dict[str, Any]] = field(default_factory=list)

    # Zaif tomonlar
    weak_areas: List[str] = field(default_factory=list)

    # Tavsiyalar
    recommendations: List[str] = field(default_factory=list)
