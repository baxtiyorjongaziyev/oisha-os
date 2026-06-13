from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ERPEvent:
    event_id: str
    event_type: str
    source: str
    entity_type: str
    entity_id: str
    occurred_at: str
    correlation_id: str
    payload: Dict[str, Any]
    raw_hash: str


@dataclass(frozen=True)
class ERPWorkflow:
    workflow_id: str
    workflow_type: str
    entity_type: str
    entity_id: str
    correlation_id: str
    status: str = "new"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ERPAction:
    action_id: str
    workflow_id: str
    action_type: str
    target: str
    payload: Dict[str, Any]
    risk_level: str
    idempotency_key: str
    expected_result: Dict[str, Any]


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    source: str
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    reason: str
