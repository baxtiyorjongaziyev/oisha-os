import asyncio
from unittest.mock import AsyncMock

from src.services.core.agent_brain import OishaBrain
from src.services.core.agent_orchestrator import AgentOrchestrator, Pipeline


def test_oisha_brain_logs_with_database_contract():
    db = AsyncMock()
    brain = OishaBrain(db=db)
    result = {"priority": "low"}

    asyncio.run(brain._log(result))

    db.log_agent_action.assert_awaited_once_with(
        user_id=0,
        action_type="agent_brain_evolve",
        data=result,
        success=True,
    )


def test_oisha_brain_uses_shared_gemini_model(monkeypatch):
    monkeypatch.delenv("GEMINI_BRAIN_MODEL", raising=False)

    assert OishaBrain().gemini_model == "gemini-2.5-flash"


def test_agent_orchestrator_logs_with_database_contract():
    db = AsyncMock()
    orchestrator = AgentOrchestrator(db=db)
    pipeline = Pipeline(id="pipeline-1", goal="verify logging")

    asyncio.run(orchestrator.run_pipeline(pipeline))

    db.log_agent_action.assert_awaited_once()
    kwargs = db.log_agent_action.await_args.kwargs
    assert kwargs["action_type"] == "orchestrator_pipeline"
    assert kwargs["data"]["id"] == "pipeline-1"
    assert kwargs["success"] is True
