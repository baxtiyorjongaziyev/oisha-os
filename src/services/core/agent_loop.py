from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.database import Database
from src.time_utils import get_local_now

ExecutorFn = Callable[["AgentTask"], Awaitable[Dict[str, Any]]]
VerifierFn = Callable[["AgentTask", Dict[str, Any]], Awaitable[Dict[str, Any]]]


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

    def __init__(self, db: Database):
        self.db = db

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
    ) -> AgentTaskResult:
        plan = self.plan_task(task)
        await self._log(task, "agent_plan", plan, success=True)

        try:
            execution = await executor(task)
        except Exception as exc:
            execution = {
                "task_id": task.task_id,
                "success": False,
                "reason": "executor_exception",
                "error": str(exc),
                "failed_at": get_local_now().isoformat(),
            }
        execution_success = bool(execution.get("success", execution.get("ok", True)))
        await self._log(task, "agent_execute", execution, success=execution_success)

        try:
            if verifier is None:
                verification = self.default_verify(task, execution)
            else:
                verification = await verifier(task, execution)
        except Exception as exc:
            verification = {
                "task_id": task.task_id,
                "success": False,
                "reason": "verifier_exception",
                "error": str(exc),
                "verified_at": get_local_now().isoformat(),
            }
        await self._log(
            task,
            "agent_verify",
            verification,
            success=bool(verification.get("success", False)),
        )

        return AgentTaskResult(
            task_id=task.task_id,
            success=bool(verification.get("success", False)),
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
            "verified_at": get_local_now().isoformat(),
        }

    async def log_stage(
        self, task: AgentTask, action_type: str, data: Dict[str, Any], success: bool
    ) -> None:
        await self._log(task, action_type, data, success)

    async def _log(
        self, task: AgentTask, action_type: str, data: Dict[str, Any], success: bool
    ) -> None:
        user_id = int(
            task.payload.get("user_id") or task.payload.get("target_user_id") or 0
        )
        payload = {
            "task_id": task.task_id,
            "task_kind": task.kind,
            "goal": task.goal,
            "requested_by": task.requested_by,
            "data": data,
        }
        await self.db.log_agent_action(user_id, action_type, payload, success=success)
