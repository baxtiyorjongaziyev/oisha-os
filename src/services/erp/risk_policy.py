from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RISK_TO_AUTONOMY = {
    "none": "A4",
    "low": "A3",
    "medium": "A2",
    "high": "A1",
    "critical": "A0",
}

AUTONOMY_ORDER = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5}

COMPLAINT_TERMS = (
    "shikoyat",
    "qaytarib bering",
    "pulni qaytar",
    "refund",
    "advokat",
    "sud",
    "aldadi",
    "firibgar",
)


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    risk_level: str
    max_autonomy: str
    requires_approval: bool = False
    escalate: bool = False
    checks: dict[str, Any] = field(default_factory=dict)


class ERPRiskPolicy:
    """Fail-closed risk matrix for ERP actions."""

    def __init__(self, db: Any):
        self.db = db

    async def evaluate(
        self,
        *,
        action_type: str,
        payload: dict[str, Any],
        module: str = "",
        client_id: str = "",
        approved: bool = False,
        autonomy_level: str = "",
    ) -> RiskDecision:
        action_type = str(action_type or "unknown").strip().casefold()
        module = str(module or action_type.split(".", 1)[0] or "unknown").strip().casefold()
        client_id = str(client_id or payload.get("client_id") or payload.get("lead_id") or "")
        message = str(payload.get("message") or payload.get("text") or "").casefold()
        risk_level = self.classify(action_type, payload)
        max_autonomy = RISK_TO_AUTONOMY[risk_level]
        current_autonomy = (
            autonomy_level
            or await self._get_state("erp:autonomy_level", "A2")
            or "A2"
        ).upper()
        if current_autonomy not in AUTONOMY_ORDER:
            current_autonomy = "A0"

        kill_reason = await self._kill_switch_reason(module, client_id)
        checks = {
            "action_type": action_type,
            "module": module,
            "client_id": client_id,
            "risk_level": risk_level,
            "current_autonomy": current_autonomy,
            "max_autonomy": max_autonomy,
            "approved": bool(approved),
        }
        if kill_reason:
            return RiskDecision(
                False,
                kill_reason,
                risk_level,
                max_autonomy,
                checks=checks,
            )

        if any(term in message for term in COMPLAINT_TERMS):
            return RiskDecision(
                False,
                "complaint_requires_owner",
                "high",
                RISK_TO_AUTONOMY["high"],
                requires_approval=True,
                escalate=True,
                checks=checks,
            )

        requires_approval = risk_level in {"high", "critical"}
        if requires_approval and not approved:
            return RiskDecision(
                False,
                "owner_approval_required",
                risk_level,
                max_autonomy,
                requires_approval=True,
                checks=checks,
            )

        if approved and requires_approval:
            return RiskDecision(
                True,
                "approved_high_risk_action",
                risk_level,
                max_autonomy,
                requires_approval=True,
                checks=checks,
            )

        if AUTONOMY_ORDER[current_autonomy] > AUTONOMY_ORDER[max_autonomy]:
            return RiskDecision(
                False,
                "autonomy_level_exceeds_risk_limit",
                risk_level,
                max_autonomy,
                requires_approval=True,
                checks=checks,
            )

        return RiskDecision(
            True,
            "risk_policy_pass",
            risk_level,
            max_autonomy,
            checks=checks,
        )

    @staticmethod
    def classify(action_type: str, payload: dict[str, Any]) -> str:
        lowered = str(action_type or "").casefold()
        text = " ".join(
            str(payload.get(key) or "").casefold()
            for key in ("message", "text", "reason", "operation")
        )
        combined = f"{lowered} {text}"
        if any(
            term in combined
            for term in (
                "refund",
                "write_off",
                "writeoff",
                "delete",
                "remove_contact",
                "remove_lead",
                "qarzni bekor",
                "pulni qaytar",
            )
        ):
            return "critical"
        if any(
            term in combined
            for term in (
                "discount",
                "chegirma",
                "contract.change",
                "change_terms",
                "shartnoma",
                "compensation",
                "kompensatsiya",
            )
        ):
            return "high"
        if any(
            term in combined
            for term in (
                "client.reply",
                "send_client",
                "telegram.send_message",
                "proposal",
                "price",
                "narx",
            )
        ):
            return "medium"
        if any(
            term in combined
            for term in (
                "calendar.confirm_meeting",
                "calendar.create",
                "amocrm.create_task",
                "amocrm.add_note",
                "airtable.update",
            )
        ):
            return "low"
        return "none"

    async def _kill_switch_reason(self, module: str, client_id: str) -> str:
        keys = [("global", "erp:kill_switch:global")]
        if module:
            keys.append((f"module:{module}", f"erp:kill_switch:module:{module}"))
        if client_id:
            keys.append((f"client:{client_id}", f"erp:kill_switch:client:{client_id}"))
        for label, key in keys:
            if await self._get_bool_state(key, False):
                return f"kill_switch_active:{label}"
        return ""

    async def _get_state(self, key: str, default: str) -> str:
        try:
            return str(await self.db.get_state(key, default) or default)
        except TypeError:
            return str(await self.db.get_state(key) or default)

    async def _get_bool_state(self, key: str, default: bool) -> bool:
        raw = await self._get_state(key, str(default).lower())
        return str(raw).strip().casefold() in {"1", "true", "yes", "on", "enabled"}
