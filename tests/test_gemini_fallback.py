from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.utils.gemini_fallback import generate_content_with_fallback


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
