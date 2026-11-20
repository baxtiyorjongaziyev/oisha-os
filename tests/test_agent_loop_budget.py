"""Loop engineering: budget, retry, timeout, eskalatsiya va trace (run_id)."""
import asyncio

from src.services.core.agent_loop import AgentTask, LoopBudget, MinimalAgentLoop
from src.services.core.agent_policy import PolicyDecision


class _AllowPolicy:
    async def evaluate_action(self, task):
        return PolicyDecision(True, "test_pass")


class _DB:
    def __init__(self):
        self.logs = []

    async def log_agent_action(self, user_id, action_type, payload, success=True):
        self.logs.append((action_type, payload, success))


def _loop():
    db = _DB()
    return MinimalAgentLoop(db, policy_engine=_AllowPolicy()), db


def _task():
    return AgentTask(task_id="t1", kind="internal_report", goal="test")


def test_default_budget_is_single_attempt_and_self_reported():
    loop, db = _loop()
    calls = []

    async def executor(task):
        calls.append(1)
        return {"success": False}

    result = asyncio.run(loop.run(_task(), executor))
    assert result.success is False
    assert len(calls) == 1
    assert result.verification["verification_mode"] == "self_reported"


def test_retries_until_independent_verifier_confirms():
    loop, db = _loop()
    attempts = []

    async def executor(task):
        attempts.append(1)
        return {"success": True, "crm_id": 7 if len(attempts) == 2 else None}

    async def verifier(task, execution):
        return {"success": execution.get("crm_id") is not None}

    result = asyncio.run(loop.run(_task(), executor, verifier, budget=LoopBudget(max_attempts=3)))
    assert result.success is True
    assert len(attempts) == 2
    assert result.verification["verification_mode"] == "independent"
    assert result.verification["attempt"] == 2


def test_non_retryable_failure_stops_and_escalates():
    loop, db = _loop()
    attempts, escalations = [], []

    async def executor(task):
        attempts.append(1)
        return {"success": True}

    async def verifier(task, execution):
        return {"success": False, "retryable": False, "reason": "lead_deleted"}

    async def escalate(task, info):
        escalations.append(info)

    result = asyncio.run(
        loop.run(_task(), executor, verifier, budget=LoopBudget(max_attempts=5), escalate=escalate)
    )
    assert result.success is False
    assert len(attempts) == 1
    assert escalations[0]["reason"] == "lead_deleted"
    assert any(a == "agent_escalate" for a, _, _ in db.logs)


def test_executor_timeout_is_reported():
    loop, db = _loop()

    async def executor(task):
        await asyncio.sleep(1)
        return {"success": True}

    result = asyncio.run(loop.run(_task(), executor, budget=LoopBudget(timeout_s=0.01)))
    assert result.success is False
    assert result.execution["reason"] == "executor_timeout"


def test_verifier_outage_does_not_replay_executor():
    loop, db = _loop()
    attempts, escalations = [], []

    async def executor(task):
        attempts.append(1)
        return {"success": True}

    async def verifier(task, execution):
        raise ConnectionError("read-back failed")

    async def escalate(task, info):
        escalations.append(info)

    result = asyncio.run(
        loop.run(_task(), executor, verifier, budget=LoopBudget(max_attempts=3), escalate=escalate)
    )
    assert result.success is False
    assert len(attempts) == 1
    assert escalations[0]["reason"] == "verifier_exception"


def test_timeout_is_not_replayed():
    loop, db = _loop()
    attempts = []

    async def executor(task):
        attempts.append(1)
        await asyncio.sleep(1)
        return {"success": True}

    asyncio.run(loop.run(_task(), executor, budget=LoopBudget(max_attempts=3, timeout_s=0.01)))
    assert len(attempts) == 1


def test_policy_is_rechecked_before_retry():
    db = _DB()

    class _FlipPolicy:
        def __init__(self):
            self.allowed = True

        async def evaluate_action(self, task):
            return PolicyDecision(self.allowed, "test_pass" if self.allowed else "auto_actions_disabled")

    policy = _FlipPolicy()
    loop = MinimalAgentLoop(db, policy_engine=policy)
    attempts = []

    async def executor(task):
        attempts.append(1)
        policy.allowed = False  # kill-switch birinchi urinish vaqtida yoqildi
        return {"success": False}

    result = asyncio.run(loop.run(_task(), executor, budget=LoopBudget(max_attempts=3)))
    assert len(attempts) == 1
    assert result.verification["reason"] == "auto_actions_disabled"


def test_all_stages_share_one_run_id():
    loop, db = _loop()

    async def executor(task):
        return {"success": True}

    asyncio.run(loop.run(_task(), executor))
    run_ids = {payload["run_id"] for _, payload, _ in db.logs}
    assert len(run_ids) == 1 and None not in run_ids
