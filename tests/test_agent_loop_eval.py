"""Scenario eval harness for MinimalAgentLoop (Planner -> Executor -> Verifier).

Each scenario pins a fake policy decision, executor and verifier, then checks the
final verdict, the reason and the audit trail. Add a row to SCENARIOS to cover
a new failure mode; no live services are touched.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable, Optional

import pytest

from src.services.core.agent_loop import AgentTask, MinimalAgentLoop
from src.services.core.agent_policy import PolicyDecision


class FakeDB:
    def __init__(self):
        self.logs = []

    async def log_agent_action(self, user_id, action_type, payload, success=True):
        self.logs.append((action_type, success))


class FakePolicy:
    def __init__(self, allowed: bool, reason: str):
        self.decision = PolicyDecision(allowed, reason, checks={})

    async def evaluate_action(self, task):
        return self.decision


async def ok_executor(task):
    return {"success": True, "sent_count": 1}


async def empty_executor(task):
    return {}


async def boom_executor(task):
    raise RuntimeError("tool down")


async def strict_verifier(task, execution):
    return {"success": execution.get("sent_count", 0) >= 2, "reason": "need_two"}


async def boom_verifier(task, execution):
    raise ValueError("verifier crashed")


@dataclass
class Scenario:
    name: str
    executor: Callable
    verifier: Optional[Callable] = None
    allowed: bool = True
    expect_success: bool = True
    expect_reason: Optional[str] = None
    expect_stages: tuple = ("agent_policy", "agent_plan", "agent_execute", "agent_verify")


SCENARIOS = [
    Scenario("happy_path", ok_executor, expect_reason="delivery_confirmed"),
    Scenario("empty_execution_is_not_success", empty_executor,
             expect_success=False, expect_reason="execution_failed"),
    Scenario("executor_exception_contained", boom_executor,
             expect_success=False, expect_reason="executor_exception"),
    Scenario("custom_verifier_rejects", ok_executor, strict_verifier,
             expect_success=False, expect_reason="need_two"),
    Scenario("verifier_exception_contained", ok_executor, boom_verifier,
             expect_success=False, expect_reason="verifier_exception"),
    Scenario("policy_block_skips_executor", boom_executor, allowed=False,
             expect_success=False, expect_reason="quiet_hours",
             expect_stages=("agent_policy", "agent_execute", "agent_verify")),
]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_agent_loop_scenario(scenario: Scenario):
    db = FakeDB()
    loop = MinimalAgentLoop(db, FakePolicy(scenario.allowed, "quiet_hours"))
    task = AgentTask(task_id="t1", kind="eval", goal="eval", payload={"user_id": 1})

    result = asyncio.run(loop.run(task, scenario.executor, scenario.verifier))

    assert result.success is scenario.expect_success
    if scenario.expect_reason:
        assert result.verification.get("reason") == scenario.expect_reason
    assert tuple(stage for stage, _ in db.logs) == scenario.expect_stages
    assert db.logs[-1][1] is scenario.expect_success
