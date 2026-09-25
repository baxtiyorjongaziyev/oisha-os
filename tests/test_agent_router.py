from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.utils.gemini_failover.models import DEFAULT_FALLBACK_MODELS

from src.agents.orchestrator import AgentOrchestrator
from src.services.utils.gemini_failover.models import DEFAULT_FALLBACK_MODELS

FIRST_FALLBACK = DEFAULT_FALLBACK_MODELS[0]


@pytest.mark.asyncio
async def test_router_recovers_from_primary_gemini_high_demand():
    models = SimpleNamespace(
        generate_content=AsyncMock(
            side_effect=[
                RuntimeError("503 UNAVAILABLE: high demand"),
                SimpleNamespace(text="researcher"),
            ]
        )
    )
    sales_agent = SimpleNamespace(
        model_configs={
            "gemini": {
                "client": SimpleNamespace(aio=SimpleNamespace(models=models)),
                "model": "gemini-2.5-flash",
            }
        }
    )
    manager = SimpleNamespace(
        get_agent=lambda agent_id: sales_agent if agent_id == "sales" else None
    )

    intent = await AgentOrchestrator(manager).determine_intent(
        "Raqobatchilar bozorini tahlil qiling"
    )

    assert intent == "researcher"
    assert [
        call.kwargs["model"]
        for call in models.generate_content.await_args_list
    ] == ["gemini-2.5-flash", FIRST_FALLBACK]


@pytest.mark.asyncio
async def test_router_cools_down_after_gemini_quota_exhaustion():
    models = SimpleNamespace(
        generate_content=AsyncMock(side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"))
    )
    sales_agent = SimpleNamespace(
        model_configs={
            "gemini": {
                "client": SimpleNamespace(aio=SimpleNamespace(models=models)),
                "model": "gemini-2.5-flash",
            }
        }
    )
    manager = SimpleNamespace(
        get_agent=lambda agent_id: sales_agent if agent_id == "sales" else None
    )
    orchestrator = AgentOrchestrator(manager)

    assert await orchestrator.determine_intent("Narxlarni yuboring") == "sales"
    first_call_count = models.generate_content.await_count
    assert first_call_count == 1 + len(DEFAULT_FALLBACK_MODELS)

    assert await orchestrator.determine_intent("Narx qancha?") == "sales"
    assert models.generate_content.await_count == first_call_count
