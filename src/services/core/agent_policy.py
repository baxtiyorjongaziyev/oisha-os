from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from src.database import Database
from src.time_utils import get_local_now, is_quiet_hours


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    checks: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "checks": dict(self.checks),
            "metadata": dict(self.metadata),
        }


class AgentPolicyEngine:
    def __init__(self, db: Database):
        self.db = db

    async def evaluate_action(self, task: Any) -> PolicyDecision:
        now = get_local_now()
        requested_by = str(getattr(task, "requested_by", "system") or "system")
        payload = dict(getattr(task, "payload", {}) or {})
        manual_override = bool(payload.get("manual_override"))

        auto_actions_enabled = await self._get_bool_state("policy:auto_actions_enabled", True)
        quiet_hours_enabled = await self._get_bool_state("policy:quiet_hours_enabled", True)
        approval_required = await self._get_bool_state(
            f"policy:require_approval:{getattr(task, 'kind', 'unknown')}",
            False,
        )
        approval_granted = await self._get_bool_state(
            f"policy:approval_granted:{getattr(task, 'kind', 'unknown')}",
            False,
        )
        allow_in_quiet_hours = bool(payload.get("allow_in_quiet_hours"))
        in_quiet_hours = quiet_hours_enabled and is_quiet_hours(now)

        checks = {
            "requested_by": requested_by,
            "manual_override": manual_override,
            "auto_actions_enabled": auto_actions_enabled,
            "quiet_hours_enabled": quiet_hours_enabled,
            "approval_required": approval_required,
            "approval_granted": approval_granted,
            "allow_in_quiet_hours": allow_in_quiet_hours,
            "in_quiet_hours": in_quiet_hours,
            "evaluated_at": now.isoformat(),
        }

        if not auto_actions_enabled and requested_by not in {"manual", "owner"} and not manual_override:
            return PolicyDecision(False, "auto_actions_disabled", checks=checks)

        if in_quiet_hours and requested_by not in {"manual", "owner"} and not allow_in_quiet_hours and not manual_override:
            return PolicyDecision(False, "quiet_hours_block", checks=checks)

        if approval_required and requested_by not in {"manual", "owner"} and not approval_granted and not manual_override:
            return PolicyDecision(False, "owner_approval_required", checks=checks)

        return PolicyDecision(True, "policy_pass", checks=checks)

    async def _get_bool_state(self, key: str, default: bool) -> bool:
        raw_value = await self.db.get_state(key, str(default).lower())
        if raw_value is None:
            return default
        normalized = str(raw_value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled"}:
            return False
        return default
