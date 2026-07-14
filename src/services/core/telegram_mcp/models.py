from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


OperationStatus = Literal[
    "pending", "executing", "cancelled", "succeeded", "failed", "expired"
]


@dataclass(frozen=True)
class PendingOperation:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    requester: str
    payload_hash: str
    risk: str
    status: OperationStatus
    created_at: datetime
    expires_at: datetime
    approved_by: int | None = None


@dataclass(frozen=True)
class ExecutionOutcome:
    status: str
    user_message: str
    badge: str
    operation_id: str
    result: Any = None
