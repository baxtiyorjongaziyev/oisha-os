import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.core.oisha_coordinator import OishaCoordinator


class _FakePipeline:
    def __init__(self, pipeline_id="p-1"):
        self.id = pipeline_id
        self.status = "done"
        self.results = {"draft_revival": "ok"}


class _FakeOrchestrator:
    def stagnated_lead_pipeline(self, user_id, lead_name):
        return _FakePipeline(f"{user_id}:{lead_name}")

    async def run_pipeline(self, pipeline):
        return pipeline


def test_coordinator_analysis_cycle_logs_execution():
    db = AsyncMock()
    db.get_state = AsyncMock(side_effect=lambda key, default=None: {
        "runtime:userbot_authorized": "true",
        "policy:auto_master": "true",
        "memory:last_goal": "support lead",
        "memory:last_action": "analysis",
        "memory:last_outcome": "ok",
    }.get(key, default))
    db.get_chat_summary = AsyncMock(return_value="Qisqa xulosa")

    brain = AsyncMock()
    brain.evolve = AsyncMock(return_value={"diagnosis": "ok", "priority": "low"})

    coordinator = OishaCoordinator(db=db, brain=brain)
    result = asyncio.run(
        coordinator.run_cycle(
            "Yangi signalni tahlil qil",
            action_type="analysis",
            payload={"user_id": 123},
            user_id=123,
        )
    )

    assert result["decision"]["allowed"] is True
    assert result["execution"]["result"]["diagnosis"] == "ok"
    assert result["snapshot"]["runtime_state"]["chat_summary"] == "Qisqa xulosa"
    db.log_agent_action.assert_awaited_once()
    assert db.log_agent_action.await_args.kwargs["action_type"] == "oisha_coordinator_cycle"


def test_coordinator_fail_safe_blocks_without_storage():
    coordinator = OishaCoordinator()
    result = asyncio.run(
        coordinator.run_cycle(
            "Leadni yangila",
            action_type="amocrm.update",
            payload={"user_id": 1},
            safety_mode="fail_safe",
        )
    )

    assert result["decision"]["allowed"] is False
    assert result["execution"]["status"] == "blocked"
    assert result["verification"]["success"] is False


def test_coordinator_pipeline_path_uses_orchestrator():
    db = AsyncMock()
    db.get_state = AsyncMock(return_value=None)
    db.get_chat_summary = AsyncMock(return_value=None)
    orchestrator = _FakeOrchestrator()

    coordinator = OishaCoordinator(db=db, agent_orchestrator=orchestrator)
    result = asyncio.run(
        coordinator.run_cycle(
            "Stagnated lead",
            action_type="pipeline",
            payload={"user_id": 5, "lead_name": "Ali"},
            user_id=5,
        )
    )

    assert result["execution"]["result"]["status"] == "done"
    assert "pipeline_id" in result["execution"]["result"]
