from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents import ai_router


@pytest.fixture(autouse=True)
def clear_router_cache():
    ai_router._cache.clear()
    yield
    ai_router._cache.clear()


@pytest.mark.asyncio
async def test_simple_analysis_uses_groq_cloudflare_ollama_without_gemini(monkeypatch):
    free_router = SimpleNamespace(
        generate_text=AsyncMock(
            return_value=SimpleNamespace(
                text="oddiy javob",
                provider="groq",
                model="llama",
                tokens_in=2,
                tokens_out=3,
            )
        )
    )
    monkeypatch.setattr(
        "src.services.utils.free_ai_router.get_free_ai_router",
        lambda: free_router,
    )
    gemini_client = AsyncMock()
    monkeypatch.setattr(ai_router, "_get_gemini_client", gemini_client)

    result = await ai_router.route(
        "Mijozni qisqa klassifikatsiya qil",
        task_type="classify",
        bypass_cache=True,
    )

    assert result["provider"] == "groq"
    assert free_router.generate_text.await_args.kwargs["providers"] == (
        "groq",
        "cloudflare",
        "ollama",
    )
    gemini_client.assert_not_called()


@pytest.mark.asyncio
async def test_complex_analysis_uses_flash_lite_then_cloudflare_ollama(monkeypatch):
    free_router = SimpleNamespace(
        generate_text=AsyncMock(
            return_value=SimpleNamespace(
                text="fallback javob",
                provider="cloudflare",
                model="@cf/llama",
                tokens_in=0,
                tokens_out=0,
            )
        )
    )
    monkeypatch.setattr(
        "src.services.utils.free_ai_router.get_free_ai_router",
        lambda: free_router,
    )
    monkeypatch.setattr(ai_router, "_get_gemini_client", lambda: object())
    monkeypatch.setattr(
        ai_router,
        "_maybe_degrade_tier",
        AsyncMock(return_value="L3"),
    )
    gemini_call = AsyncMock(side_effect=RuntimeError("429 quota"))
    monkeypatch.setattr(ai_router, "_call_gemini", gemini_call)
    monkeypatch.setattr(ai_router.asyncio, "sleep", AsyncMock())

    result = await ai_router.route(
        "Murakkab muzokarani tahlil qil",
        task_type="reason",
        bypass_cache=True,
    )

    assert gemini_call.await_args.kwargs["model"] == ai_router.settings.FREE_AI_GEMINI_MODEL
    assert free_router.generate_text.await_args.kwargs["providers"] == (
        "cloudflare",
        "ollama",
    )
    assert result["provider"] == "cloudflare"
