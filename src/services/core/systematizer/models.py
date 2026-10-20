"""Data models for Oisha-OS Systematizer and PatternDetector."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PatternType(str, Enum):
    """Categorization of detected recurring team behaviors."""

    FAQ_QUESTION = "faq_question"
    ROUTINE_TASK = "routine_task"
    CRM_OBJECTION = "crm_objection"
    FINANCE_EXPENSE = "finance_expense"
    MANAGER_REPLY = "manager_reply"


class AutomationStrategy(str, Enum):
    """Recommended systematization method for a detected pattern."""

    AI_AUTO_REPLY = "ai_auto_reply"
    TASK_TEMPLATE = "task_template"
    CRM_TRIGGER = "crm_trigger"
    SKILL_SOP = "skill_sop"
    FINANCE_RULE = "finance_rule"


class ProposalStatus(str, Enum):
    """Review and lifecycle state of a systematization proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


@dataclass
class PatternSignature:
    """Core matching signature and linguistic hash of a pattern."""

    raw_tokens: tuple[str, ...]
    normalized_phrase: str
    category: PatternType

    def __post_init__(self) -> None:
        if not self.normalized_phrase:
            self.normalized_phrase = " ".join(self.raw_tokens)


@dataclass
class DetectedPattern:
    """A recurring operational behavior identified across team channels."""

    pattern_id: str
    pattern_type: PatternType
    title: str
    frequency: int
    sample_texts: List[str] = field(default_factory=list)
    interlocutors: List[str] = field(default_factory=list)
    impact_score: float = 1.0
    first_seen: Optional[datetime.datetime] = None
    last_seen: Optional[datetime.datetime] = None
    confidence: float = 0.85
    suggested_strategy: AutomationStrategy = AutomationStrategy.AI_AUTO_REPLY
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize pattern into a clean dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "title": self.title,
            "frequency": self.frequency,
            "sample_texts": self.sample_texts[:5],
            "interlocutor_count": len(self.interlocutors),
            "impact_score": round(self.impact_score, 2),
            "confidence": round(self.confidence, 2),
            "strategy": self.suggested_strategy.value,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


@dataclass
class SystematizationProposal:
    """Concrete proposal turning a detected repetition into an automated system."""

    proposal_id: str
    pattern_id: str
    title: str
    strategy: AutomationStrategy
    problem_statement: str
    solution_blueprint: str
    time_saved_weekly_minutes: int
    target_skill_or_handler: str
    status: ProposalStatus = ProposalStatus.PENDING
    draft_sop: Optional[str] = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize proposal for API or Command Center presentation."""
        return {
            "proposal_id": self.proposal_id,
            "pattern_id": self.pattern_id,
            "title": self.title,
            "strategy": self.strategy.value,
            "problem_statement": self.problem_statement,
            "solution_blueprint": self.solution_blueprint,
            "time_saved_weekly_minutes": self.time_saved_weekly_minutes,
            "target_skill_or_handler": self.target_skill_or_handler,
            "status": self.status.value,
            "draft_sop": self.draft_sop,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SystematizationReport:
    """Comprehensive executive audit of team repetitions and automation opportunities."""

    audit_timestamp: datetime.datetime
    scanned_messages_count: int
    scanned_tasks_count: int
    scanned_finance_count: int
    scanned_crm_count: int
    patterns: List[DetectedPattern] = field(default_factory=list)
    proposals: List[SystematizationProposal] = field(default_factory=list)

    @property
    def total_scanned_items(self) -> int:
        return (
            self.scanned_messages_count
            + self.scanned_tasks_count
            + self.scanned_finance_count
            + self.scanned_crm_count
        )

    @property
    def estimated_time_saved_hours_weekly(self) -> float:
        total_mins = sum(p.time_saved_weekly_minutes for p in self.proposals)
        return round(total_mins / 60.0, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit report into dashboard-ready payload."""
        return {
            "audit_timestamp": self.audit_timestamp.isoformat(),
            "total_scanned_items": self.total_scanned_items,
            "scanned_breakdown": {
                "messages": self.scanned_messages_count,
                "tasks": self.scanned_tasks_count,
                "finance": self.scanned_finance_count,
                "crm": self.scanned_crm_count,
            },
            "patterns_count": len(self.patterns),
            "proposals_count": len(self.proposals),
            "estimated_weekly_saved_hours": self.estimated_time_saved_hours_weekly,
            "patterns": [p.to_dict() for p in self.patterns],
            "proposals": [pr.to_dict() for pr in self.proposals],
        }
