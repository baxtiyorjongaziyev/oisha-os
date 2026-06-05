from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents.support_agent import SupportAgent
from src.services.utils.gemini_fallback import (
    GeminiModelCooldownError,
    generate_content_with_fallback,
    reset_model_quota_cooldowns,
)


@pytest.fixture(autouse=True)
def clear_model_quota_cooldowns():
    reset_model_quota_cooldowns()
    yield
    reset_model_quota_cooldowns()


@pytest.mark.asyncio
async def test_generate_content_recovers_with_fallback_model():
    models = SimpleNamespace(
        generate_content=AsyncMock(
            side_effect=[
                RuntimeError("503 UNAVAILABLE: model is in high demand"),
                SimpleNamespace(text="ok"),
            ]
        )
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    response, model = await generate_content_with_fallback(
        client,
        primary_model="gemini-2.5-flash",
        contents="hello",
    )

    assert response.text == "ok"
    assert model == "gemini-2.5-flash-lite"
    assert [
        call.kwargs["model"]
        for call in models.generate_content.await_args_list
    ] == ["gemini-2.5-flash", "gemini-2.5-flash-lite"]


@pytest.mark.asyncio
async def test_generate_content_does_not_retry_permanent_error():
    models = SimpleNamespace(
        generate_content=AsyncMock(side_effect=RuntimeError("400 invalid prompt"))
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    with pytest.raises(RuntimeError, match="invalid prompt"):
        await generate_content_with_fallback(
            client,
            primary_model="gemini-2.5-flash",
            contents="hello",
        )

    models.generate_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_content_skips_primary_model_during_quota_cooldown():
    models = SimpleNamespace(
        generate_content=AsyncMock(
            side_effect=[
                RuntimeError("429 RESOURCE_EXHAUSTED: GenerateRequestsPerDay"),
                SimpleNamespace(text="fallback"),
                SimpleNamespace(text="fallback again"),
            ]
        )
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    first_response, first_model = await generate_content_with_fallback(
        client,
        primary_model="gemini-2.5-flash",
        contents="first",
    )
    second_response, second_model = await generate_content_with_fallback(
        client,
        primary_model="gemini-2.5-flash",
        contents="second",
    )

    assert first_response.text == "fallback"
    assert second_response.text == "fallback again"
    assert first_model == second_model == "gemini-2.5-flash-lite"
    assert [
        call.kwargs["model"] for call in models.generate_content.await_args_list
    ] == [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-lite",
    ]


@pytest.mark.asyncio
async def test_generate_content_fails_fast_when_all_models_are_cooling_down():
    models = SimpleNamespace(
        generate_content=AsyncMock(
            side_effect=RuntimeError("429 RESOURCE_EXHAUSTED: GenerateRequestsPerDay")
        )
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    with pytest.raises(RuntimeError, match="RESOURCE_EXHAUSTED"):
        await generate_content_with_fallback(
            client,
            primary_model="gemini-2.5-flash",
            contents="first",
        )

    models.generate_content.reset_mock()

    with pytest.raises(GeminiModelCooldownError, match="cooling down"):
        await generate_content_with_fallback(
            client,
            primary_model="gemini-2.5-flash",
            contents="second",
        )

    models.generate_content.assert_not_awaited()


@pytest.mark.asyncio
async def test_base_agent_does_not_expose_internal_429_message():
    agent = SupportAgent("support", "system", {})
    agent.model_configs["gemini"]["client"] = object()
    agent.safe_ai_call = AsyncMock(return_value=None)

    reply = await agent.call_ai_with_fallback([], current_user_id=123)

    assert reply == ""
    assert "429" not in reply
