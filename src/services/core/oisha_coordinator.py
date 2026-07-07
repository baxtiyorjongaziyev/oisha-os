from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from src.context import app_ctx
from src.services.core.agent_verifier import ActionOutcomeVerifier
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


@dataclass
class CoordinationPlan:
    goal: str
    action_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    safety_mode: str = "fail_open"
    requires_verification: bool = True


class OishaCoordinator:
    """Central planning/decision/execution layer for Oisha."""

    def __init__(
        self,
        *,
        db=None,
        agent_orchestrator=None,
        brain=None,
        meeting_scheduler=None,
        verifier=None,
    ):
        self.db = db
        self.agent_orchestrator = agent_orchestrator
        self.brain = brain
        self.meeting_scheduler = meeting_scheduler
        self.verifier = verifier or ActionOutcomeVerifier()

    def _runtime_snapshot(self) -> Dict[str, Any]:
        snapshot = {
            "captured_at": get_local_now().isoformat(),
            "has_db": bool(self.db),
            "has_orchestrator": bool(self.agent_orchestrator),
            "has_brain": bool(self.brain),
            "has_meeting_scheduler": bool(self.meeting_scheduler),
        }
        if self.db and hasattr(self.db, "get_state"):
            snapshot["runtime_state"] = {}
        return snapshot

    async def build_state_snapshot(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        snapshot = self._runtime_snapshot()
        snapshot["user_id"] = user_id
        if not self.db:
            return snapshot

        state: Dict[str, Any] = {}
        keys = [
            "runtime:userbot_authorized",
            "policy:auto_master",
            "memory:last_goal",
            "memory:last_action",
            "memory:last_outcome",
        ]
        for key in keys:
            try:
                state[key] = await self.db.get_state(key, None)
            except Exception as exc:
                logger.warning("[COORDINATOR] state lookup failed for %s: %s", key, exc)
                state[key] = None

        if user_id is not None:
            try:
                state["chat_summary"] = await self.db.get_chat_summary(user_id)
            except Exception as exc:
                logger.warning("[COORDINATOR] summary lookup failed for %s: %s", user_id, exc)
                state["chat_summary"] = None

        snapshot["runtime_state"] = state
        return snapshot

    def plan(self, goal: str, *, action_type: str, payload: Optional[Dict[str, Any]] = None) -> CoordinationPlan:
        return CoordinationPlan(goal=goal, action_type=action_type, payload=payload or {})

    def decide(self, plan: CoordinationPlan, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        action_type = plan.action_type
        if plan.safety_mode == "fail_safe" and not snapshot.get("has_db"):
            return {"allowed": False, "reason": "storage_unavailable", "mode": plan.safety_mode}
        if action_type in {"telegram.notify", "amocrm.update"}:
            return {"allowed": True, "reason": "direct_business_action", "mode": plan.safety_mode}
        if action_type == "analysis":
            return {"allowed": True, "reason": "analysis_only", "mode": plan.safety_mode}
        return {"allowed": bool(snapshot.get("has_orchestrator") or snapshot.get("has_brain")), "reason": "requires_orchestrator_or_brain", "mode": plan.safety_mode}

    async def execute(self, plan: CoordinationPlan, decision: Dict[str, Any]) -> Dict[str, Any]:
        if not decision.get("allowed"):
            return {"success": False, "status": "blocked", "reason": decision.get("reason")}

        result: Dict[str, Any]
        if plan.action_type == "analysis" and self.brain:
            result = await self.brain.evolve(task=plan.goal)
        elif self.agent_orchestrator and plan.action_type == "pipeline":
            pipeline = self.agent_orchestrator.stagnated_lead_pipeline(
                str(plan.payload.get("user_id", "unknown")),
                str(plan.payload.get("lead_name", plan.goal)),
            )
            pipeline = await self.agent_orchestrator.run_pipeline(pipeline)
            result = {"pipeline_id": pipeline.id, "status": pipeline.status, "results": pipeline.results}
        elif plan.action_type == "meeting" and self.meeting_scheduler:
            result = {"status": "scheduled", "scheduler": type(self.meeting_scheduler).__name__}
        else:
            result = {"status": "noop", "goal": plan.goal}

        return {"success": True, "status": "executed", "result": result}

    async def verify(self, plan: CoordinationPlan, execution: Dict[str, Any]) -> Dict[str, Any]:
        if not plan.requires_verification:
            return {"success": True, "verification_mode": "skipped", "reason": "not_required"}
        if "result" in execution and isinstance(execution["result"], dict) and "tool_results" in execution["result"]:
            return await self.verifier.verify(
                type("Task", (), {"task_id": plan.action_type})(),
                execution["result"],
            )
        return {
            "success": bool(execution.get("success")),
            "verification_mode": "coordinator_result",
            "reason": execution.get("reason") or "execution_completed",
            "verified_at": get_local_now().isoformat(),
        }

    async def log(self, plan: CoordinationPlan, snapshot: Dict[str, Any], decision: Dict[str, Any], execution: Dict[str, Any], verification: Dict[str, Any]) -> None:
        if not self.db or not hasattr(self.db, "log_agent_action"):
            return
        payload = {
            "goal": plan.goal,
            "action_type": plan.action_type,
            "plan": {
                "payload": plan.payload,
                "safety_mode": plan.safety_mode,
                "requires_verification": plan.requires_verification,
            },
            "snapshot": snapshot,
            "decision": decision,
            "execution": execution,
            "verification": verification,
            "logged_at": datetime.now().isoformat(),
        }
        await self.db.log_agent_action(
            user_id=int(plan.payload.get("user_id") or 0),
            action_type="oisha_coordinator_cycle",
            data=payload,
            success=bool(verification.get("success")),
        )

    async def run_cycle(self, goal: str, *, action_type: str, payload: Optional[Dict[str, Any]] = None, user_id: Optional[int] = None, safety_mode: str = "fail_open") -> Dict[str, Any]:
        plan = self.plan(goal, action_type=action_type, payload=payload)
        plan.safety_mode = safety_mode
        snapshot = await self.build_state_snapshot(user_id=user_id)
        decision = self.decide(plan, snapshot)
        execution = await self.execute(plan, decision)
        verification = await self.verify(plan, execution)
        await self.log(plan, snapshot, decision, execution, verification)
        return {
            "plan": plan,
            "snapshot": snapshot,
            "decision": decision,
            "execution": execution,
            "verification": verification,
        }


def get_coordinator(**kwargs: Any) -> OishaCoordinator:
    coordinator = getattr(app_ctx, "central_coordinator", None)
    if coordinator is None:
        coordinator = OishaCoordinator(**kwargs)
        app_ctx.central_coordinator = coordinator
    return coordinator
