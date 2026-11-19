from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.database import Database
from src.services.core.agent_policy import AgentPolicyEngine, PolicyDecision
from src.time_utils import get_local_now
import logging
logger = logging.getLogger(__name__)

ExecutorFn = Callable[["AgentTask"], Awaitable[Dict[str, Any]]]
VerifierFn = Callable[["AgentTask", Dict[str, Any]], Awaitable[Dict[str, Any]]]
EscalateFn = Callable[["AgentTask", Dict[str, Any]], Awaitable[None]]


@dataclass
class LoopBudget:
    """Loop chegaralari. Default qiymatlar eski bir martalik xatti-harakatni saqlaydi.

    max_attempts: execute+verify urinishlari soni (>=1).
    timeout_s: bitta executor chaqiruvi uchun vaqt limiti (None = cheksiz).
    """

    max_attempts: int = 1
    timeout_s: Optional[float] = None

    def __post_init__(self) -> None:
        self.max_attempts = max(1, int(self.max_attempts))


@dataclass
class AgentTask:
    task_id: str
    kind: str
    goal: str
    payload: Dict[str, Any] = field(default_factory=dict)
    planner_notes: List[str] = field(default_factory=list)
    requested_by: str = "system"


@dataclass
class AgentTaskResult:
    task_id: str
    success: bool
    plan: Dict[str, Any]
    execution: Dict[str, Any]
    verification: Dict[str, Any]
    finished_at: str


class MinimalAgentLoop:
    """Roadmapdagi Planner -> Executor -> Verifier minimal sikli."""

    def __init__(self, db: Database, policy_engine: Optional[AgentPolicyEngine] = None):
        self.db = db
        self.policy_engine = policy_engine or AgentPolicyEngine(db)

    def plan_task(self, task: AgentTask) -> Dict[str, Any]:
        steps = task.planner_notes or [
            f"{task.kind} vazifasi bajariladi",
            "natija tekshiriladi",
        ]
        return {
            "task_id": task.task_id,
            "kind": task.kind,
            "goal": task.goal,
            "steps": steps,
            "requested_by": task.requested_by,
            "planned_at": get_local_now().isoformat(),
        }

    async def run(
        self,
        task: AgentTask,
        executor: ExecutorFn,
        verifier: Optional[VerifierFn] = None,
        budget: Optional[LoopBudget] = None,
        escalate: Optional[EscalateFn] = None,
    ) -> AgentTaskResult:
        budget = budget or LoopBudget()
        run_id = uuid.uuid4().hex[:12]
        decision = await self.policy_engine.evaluate_action(task)
        await self._log(task, "agent_policy", decision.to_payload(), success=decision.allowed, run_id=run_id)
        if not decision.allowed:
            return await self._policy_blocked_result(task, decision, run_id=run_id)

        plan = self.plan_task(task)
        plan["run_id"] = run_id
        plan["budget"] = {"max_attempts": budget.max_attempts, "timeout_s": budget.timeout_s}
        await self._log(task, "agent_plan", plan, success=True, run_id=run_id)

        execution: Dict[str, Any] = {}
        verification: Dict[str, Any] = {}
        attempt = 0
        for attempt in range(1, budget.max_attempts + 1):
            execution = await self._execute(task, executor, budget, attempt)
            execution_success = bool(execution.get("success", execution.get("ok", True)))
            await self._log(task, "agent_execute", execution, success=execution_success, run_id=run_id)

            verification = await self._verify(task, execution, verifier)
            verification["attempt"] = attempt
            verified = bool(verification.get("success", False))
            await self._log(task, "agent_verify", verification, success=verified, run_id=run_id)

            # Toʻxtash shartlari: tasdiqlandi yoki verifier qayta urinishni taqiqladi.
            if verified or verification.get("retryable") is False:
                break

        success = bool(verification.get("success", False))
        if not success and escalate is not None:
            escalation = {
                "task_id": task.task_id,
                "run_id": run_id,
                "attempts": attempt,
                "reason": verification.get("reason") or "verification_failed",
            }
            await self._log(task, "agent_escalate", escalation, success=False, run_id=run_id)
            try:
                await escalate(task, escalation)
            except Exception:
                logger.error("Escalation hook failed in %s", __name__, exc_info=True)

        return AgentTaskResult(
            task_id=task.task_id,
            success=success,
            plan=plan,
            execution=execution,
            verification=verification,
            finished_at=get_local_now().isoformat(),
        )

    async def _execute(
        self, task: AgentTask, executor: ExecutorFn, budget: LoopBudget, attempt: int
    ) -> Dict[str, Any]:
        started = time.monotonic()
        try:
            if budget.timeout_s is not None:
                execution = await asyncio.wait_for(executor(task), timeout=budget.timeout_s)
            else:
                execution = await executor(task)
        except asyncio.TimeoutError:
            execution = {
                "task_id": task.task_id,
                "success": False,
                "reason": "executor_timeout",
                "failed_at": get_local_now().isoformat(),
            }
        except Exception as exc:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            execution = {
                "task_id": task.task_id,
                "success": False,
                "reason": "executor_exception",
                "error": str(exc),
                "failed_at": get_local_now().isoformat(),
            }
        execution = dict(execution or {})
        execution["attempt"] = attempt
        execution["duration_ms"] = int((time.monotonic() - started) * 1000)
        return execution

    async def _verify(
        self,
        task: AgentTask,
        execution: Dict[str, Any],
        verifier: Optional[VerifierFn],
    ) -> Dict[str, Any]:
        try:
            if verifier is None:
                return self.default_verify(task, execution)
            verification = dict(await verifier(task, execution) or {})
            verification.setdefault("verification_mode", "independent")
            return verification
        except Exception as exc:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {
                "task_id": task.task_id,
                "success": False,
                "reason": "verifier_exception",
                "error": str(exc),
                "verification_mode": "independent",
                "verified_at": get_local_now().isoformat(),
            }

    async def _policy_blocked_result(
        self, task: AgentTask, decision: PolicyDecision, run_id: Optional[str] = None
    ) -> AgentTaskResult:
        plan = self.plan_task(task)
        execution = {
            "task_id": task.task_id,
            "success": False,
            "reason": decision.reason,
            "policy": decision.to_payload(),
            "blocked_at": get_local_now().isoformat(),
        }
        verification = {
            "task_id": task.task_id,
            "success": False,
            "reason": decision.reason,
            "verification_mode": "policy_gate",
            "verified_at": get_local_now().isoformat(),
        }
        await self._log(task, "agent_execute", execution, success=False, run_id=run_id)
        await self._log(task, "agent_verify", verification, success=False, run_id=run_id)
        return AgentTaskResult(
            task_id=task.task_id,
            success=False,
            plan=plan,
            execution=execution,
            verification=verification,
            finished_at=get_local_now().isoformat(),
        )

    def default_verify(
        self, task: AgentTask, execution: Dict[str, Any]
    ) -> Dict[str, Any]:
        sent_count = int(execution.get("sent_count", 0) or 0)
        success = bool(execution.get("success", execution.get("ok", sent_count > 0)))
        return {
            "task_id": task.task_id,
            "success": success,
            "sent_count": sent_count,
            "reason": execution.get("reason")
            or ("delivery_confirmed" if success else "execution_failed"),
            # Maker == checker: executor natijasini oʻzi tasdiqlagan.
            # Yangi agentlar mustaqil verifier berishi kerak.
            "verification_mode": "self_reported",
            "verified_at": get_local_now().isoformat(),
        }

    async def log_stage(
        self, task: AgentTask, action_type: str, data: Dict[str, Any], success: bool
    ) -> None:
        await self._log(task, action_type, data, success)

    async def _log(
        self,
        task: AgentTask,
        action_type: str,
        data: Dict[str, Any],
        success: bool,
        run_id: Optional[str] = None,
    ) -> None:
        user_id = int(
            task.payload.get("user_id") or task.payload.get("target_user_id") or 0
        )
        payload = {
            "task_id": task.task_id,
            "task_kind": task.kind,
            "goal": task.goal,
            "requested_by": task.requested_by,
            "run_id": run_id,
            "data": data,
        }
        await self.db.log_agent_action(user_id, action_type, payload, success=success)
