"""Harness eval: AgentPolicyEngine uchun "oltin toʻplam".

Har bir holat tests/evals/policy_golden.json da. Policy yoki prompt o'zgarsa,
xavfsizlik qarorlari jim oʻzgarib ketmasligi uchun CI shu yerda qizil bo'ladi.
Yangi hodisa (incident) bo'lsa — avval shu faylga holat qoʻshing, keyin tuzating.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.services.core import agent_policy
from src.services.core.agent_loop import AgentTask
from src.services.core.agent_policy import AgentPolicyEngine
from src.time_utils import get_local_now

CASES = json.loads(
    (Path(__file__).parent / "evals" / "policy_golden.json").read_text(encoding="utf-8")
)

_TZ = get_local_now().tzinfo
WHEN = {
    "weekday_noon": datetime(2026, 11, 18, 12, 0, tzinfo=_TZ),  # chorshanba
    "weekday_night": datetime(2026, 11, 18, 23, 30, tzinfo=_TZ),
    "sunday_noon": datetime(2026, 11, 22, 12, 0, tzinfo=_TZ),
}


class _StateDB:
    def __init__(self, state):
        self.state = state

    async def get_state(self, key, default=None):
        return self.state.get(key, default)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_policy_golden_case(case, monkeypatch):
    monkeypatch.setattr(agent_policy, "get_local_now", lambda: WHEN[case["when"]])
    engine = AgentPolicyEngine(_StateDB(case["state"]))
    task = AgentTask(
        task_id="eval",
        kind=case["kind"],
        goal="eval",
        payload=case["payload"],
        requested_by=case["requested_by"],
    )
    decision = asyncio.run(engine.evaluate_action(task))
    assert decision.reason == case["expect"], decision.to_payload()
