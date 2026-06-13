from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from src.database import Database
from src.services.erp.approval_service import ApprovalService
from src.services.erp.risk_policy import ERPRiskPolicy
from src.time_utils import get_local_now, is_quiet_hours

CLIENT_FACING_KINDS = {
    "autonomous_negotiation",
    "client_message",
    "send_client_message",
    "telegram_userbot_dm",
    "userbot_client_reply",
}

CLIENT_TARGETS = {"client", "customer", "lead", "prospect", "telegram_dm"}

SENSITIVE_NEGOTIATION_WORDS = {
    "chegirma",
    "discount",
    "narx",
    "price",
    "to'lov",
    "tolov",
    "payment",
    "shartnoma",
    "contract",
    "kafolat",
    "guarantee",
    "muddat",
    "deadline",
}


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
    def __init__(
        self,
        db: Database,
        risk_policy: ERPRiskPolicy | None = None,
        approval_service: ApprovalService | None = None,
    ):
        self.db = db
        self.risk_policy = risk_policy or ERPRiskPolicy(db)
        self.approval_service = approval_service

    async def evaluate_action(self, task: Any) -> PolicyDecision:
        now = get_local_now()
        requested_by = str(getattr(task, "requested_by", "system") or "system")
        task_kind = str(getattr(task, "kind", "unknown") or "unknown")
        payload = dict(getattr(task, "payload", {}) or {})
        manual_override = bool(payload.get("manual_override"))
        # Approval flags inside an action payload are not trusted. Only a
        # persisted ApprovalService decision or a direct owner/manual request
        # can authorize a sensitive action.
        owner_approved = False
        action_id = str(payload.get("action_id") or payload.get("erp_action_id") or "")
        if action_id and self.approval_service is not None:
            owner_approved = owner_approved or await self.approval_service.is_approved(
                action_id
            )
        target = str(payload.get("target") or payload.get("channel") or "").lower()
        message_text = str(payload.get("text") or payload.get("message") or "").lower()
        confidence = self._safe_float(payload.get("confidence"), 1.0)
        userbot_available = payload.get("userbot_available")
        if userbot_available is None:
            userbot_available = await self._get_bool_state(
                "runtime:userbot_authorized", False
            )

        client_facing = task_kind in CLIENT_FACING_KINDS or target in CLIENT_TARGETS
        sensitive_terms = sorted(
            term for term in SENSITIVE_NEGOTIATION_WORDS if term in message_text
        )

        auto_actions_enabled = await self._get_bool_state(
            "policy:auto_actions_enabled", True
        )
        quiet_hours_enabled = await self._get_bool_state(
            "policy:quiet_hours_enabled", True
        )
        approval_required = await self._get_bool_state(
            f"policy:require_approval:{task_kind}",
            False,
        )
        approval_granted = await self._get_bool_state(
            f"policy:approval_granted:{task_kind}",
            False,
        )
        allow_in_quiet_hours = bool(payload.get("allow_in_quiet_hours"))
        in_quiet_hours = quiet_hours_enabled and is_quiet_hours(now)

        checks = {
            "requested_by": requested_by,
            "manual_override": manual_override,
            "owner_approved": owner_approved,
            "auto_actions_enabled": auto_actions_enabled,
            "quiet_hours_enabled": quiet_hours_enabled,
            "approval_required": approval_required,
            "approval_granted": approval_granted,
            "allow_in_quiet_hours": allow_in_quiet_hours,
            "in_quiet_hours": in_quiet_hours,
            "client_facing": client_facing,
            "target": target,
            "confidence": confidence,
            "userbot_available": bool(userbot_available),
            "sensitive_terms": sensitive_terms,
            "evaluated_at": now.isoformat(),
        }

        risk_decision = await self.risk_policy.evaluate(
            action_type=str(payload.get("action_type") or task_kind),
            payload=payload,
            module=str(payload.get("module") or target or task_kind),
            client_id=str(payload.get("client_id") or payload.get("lead_id") or ""),
            approved=owner_approved or requested_by in {"manual", "owner"},
        )
        checks["erp_risk"] = {
            "risk_level": risk_decision.risk_level,
            "max_autonomy": risk_decision.max_autonomy,
            "requires_approval": risk_decision.requires_approval,
            "escalate": risk_decision.escalate,
        }
        if not risk_decision.allowed:
            return PolicyDecision(
                False,
                risk_decision.reason,
                checks=checks,
                metadata={"escalate": risk_decision.escalate},
            )

        if (
            not auto_actions_enabled
            and requested_by not in {"manual", "owner"}
            and not manual_override
        ):
            return PolicyDecision(False, "auto_actions_disabled", checks=checks)

        if (
            in_quiet_hours
            and requested_by not in {"manual", "owner"}
            and not allow_in_quiet_hours
            and not manual_override
        ):
            return PolicyDecision(False, "quiet_hours_block", checks=checks)

        if (
            approval_required
            and requested_by not in {"manual", "owner"}
            and not approval_granted
            and not manual_override
        ):
            return PolicyDecision(False, "owner_approval_required", checks=checks)

        if client_facing and not bool(userbot_available):
            return PolicyDecision(
                False, "userbot_unavailable_for_client_action", checks=checks
            )

        if (
            client_facing
            and confidence < 0.85
            and requested_by not in {"manual", "owner"}
            and not owner_approved
        ):
            return PolicyDecision(
                False, "low_confidence_client_action_requires_owner", checks=checks
            )

        if (
            client_facing
            and sensitive_terms
            and requested_by not in {"manual", "owner"}
            and not owner_approved
        ):
            return PolicyDecision(
                False, "sensitive_negotiation_requires_owner", checks=checks
            )

        return PolicyDecision(True, "policy_pass", checks=checks)

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

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
