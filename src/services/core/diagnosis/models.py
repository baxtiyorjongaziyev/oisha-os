"""
Data models and taxonomy constants for Oisha Self-Diagnosis and Self-Improvement.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

@dataclass
class ImprovementProposal:
    """Bir taklif — muammo + yechim + meta."""

    id: str  # "DIAG-2026-07-15-001"
    category: str  # error_fix | health | feature_gap | code_quality | performance
    severity: str  # critical | high | medium | low
    title: str  # Qisqa sarlavha
    problem: str  # Muammo tavsifi
    proposed_solution: str  # Yechim taklifi
    affected_files: List[str] = field(default_factory=list)
    estimated_effort: str = "1h"  # 15min | 30min | 1h | 4h | 1d
    suggested_agent: str = "Coordinator"
    evidence: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: str = (
        "proposed"  # proposed | accepted | in_progress | done | rejected | deferred
    )
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    rejection_reason: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = get_local_now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ImprovementProposal":
        data = dict(data)
        # Handle JSON string fields
        if isinstance(data.get("affected_files"), str):
            try:
                data["affected_files"] = json.loads(data["affected_files"])
            except (json.JSONDecodeError, TypeError):
                data["affected_files"] = []
        if isinstance(data.get("evidence"), str):
            try:
                data["evidence"] = json.loads(data["evidence"])
            except (json.JSONDecodeError, TypeError):
                data["evidence"] = {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Severity & category constants
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SEVERITY_EMOJI = {
    SEVERITY_CRITICAL: "🔴",
    SEVERITY_HIGH: "🟡",
    SEVERITY_MEDIUM: "🔵",
    SEVERITY_LOW: "⚪",
}

CATEGORY_ERROR = "error_fix"
CATEGORY_HEALTH = "health"
CATEGORY_FEATURE = "feature_gap"
CATEGORY_CODE = "code_quality"
CATEGORY_PERF = "performance"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|secret|password|api[_-]?key)(\s*[:=]\s*)\S+"),
    re.compile(r"\b\d{9,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*"),
)


# ---------------------------------------------------------------------------
# Main diagnosis engine
# ---------------------------------------------------------------------------


