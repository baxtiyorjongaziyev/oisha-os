from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NegotiationVerification:
    success: bool
    executed_actions: int
    successful_actions: int
    failed_actions: List[Dict[str, Any]] = field(default_factory=list)
    missing_actions: List[str] = field(default_factory=list)
    resulting_status: str = ""
    notes: List[str] = field(default_factory=list)

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


class NegotiationOutcomeVerifier:
    def verify(
        self,
        action_results: List[Dict[str, Any]],
        resulting_status: str = "",
        planned_actions: Optional[List[Dict[str, Any]]] = None,
    ) -> NegotiationVerification:
        executed_actions = len(action_results)
        failed_actions = [
            item for item in action_results if not item.get("success", False)
        ]
        successful_actions = executed_actions - len(failed_actions)
        notes: List[str] = []
        missing_actions: List[str] = []

        if planned_actions:
            successful_names = [
                item.get("action")
                for item in action_results
                if item.get("success", False)
            ]
            for planned in planned_actions:
                action_name = planned.get("name")
                if action_name and action_name not in successful_names:
                    missing_actions.append(action_name)

        if executed_actions == 0:
            notes.append("no_side_effect_actions_executed")
        if failed_actions:
            notes.append("partial_or_failed_execution")
        else:
            notes.append("all_actions_succeeded")
        if missing_actions:
            notes.append("planned_actions_missing")

        success = len(failed_actions) == 0 and len(missing_actions) == 0

        return NegotiationVerification(
            success=success,
            executed_actions=executed_actions,
            successful_actions=successful_actions,
            failed_actions=failed_actions,
            missing_actions=missing_actions,
            resulting_status=resulting_status,
            notes=notes,
        )
