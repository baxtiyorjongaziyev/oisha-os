from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    status: str = "ok"
    sent_count: int = 0
    group_message_id: Optional[int] = None
    direct_message_ids: List[int] = field(default_factory=list)
    delivered_to: List[int] = field(default_factory=list)
    failed_targets: List[Dict[str, Any]] = field(default_factory=list)
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "status": self.status,
            "sent_count": self.sent_count,
            "group_message_id": self.group_message_id,
            "direct_message_ids": list(self.direct_message_ids),
            "delivered_to": list(self.delivered_to),
            "failed_targets": list(self.failed_targets),
            "reason": self.reason,
            "metadata": dict(self.metadata),
            "raw": dict(self.raw),
        }


class ToolAdapter(Protocol):
    tool_name: str


class ToolRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, ToolAdapter] = {}

    def register(self, name: str, adapter: ToolAdapter) -> ToolAdapter:
        self._adapters[name] = adapter
        return adapter

    def get(self, name: str) -> ToolAdapter:
        if name not in self._adapters:
            raise KeyError(f"Tool adapter not registered: {name}")
        return self._adapters[name]

    def has(self, name: str) -> bool:
        return name in self._adapters

    def list_names(self) -> List[str]:
        return sorted(self._adapters.keys())
