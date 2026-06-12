from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from src.services.utils.free_ai_router import FreeAIProviderRouter


def _settings(**overrides):
    values = {
        "GROQ_API_KEY": "",
        "GROQ_TEXT_MODEL": "groq-text",
        "GROQ_WHISPER_MODEL": "groq-whisper",
        "CLOUDFLARE_ACCOUNT_ID": "",
        "CLOUDFLARE_AI_API_TOKEN": "",
        "CLOUDFLARE_TEXT_MODEL": "@cf/text",
        "CLOUDFLARE_WHISPER_MODEL": "@cf/whisper",
        "OLLAMA_BASE_URL": "",
        "OLLAMA_TEXT_MODEL": "qwen",
        "FREE_AI_PROVIDER_TIMEOUT_SECONDS": 2,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("POST", "https://example.test"),
    )


@pytest.mark.asyncio
async def test_groq_text_is_primary():
    client = SimpleNamespace(
        request=AsyncMock(
            return_value=_response(
                200,
                {
                    "choices": [{"message": {"content": "groq javob"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3},
                },
            )
        )
    )
    router = FreeAIProviderRouter(_settings(GROQ_API_KEY="key"), client)

    result = await router.generate_text("salom")

    assert result.provider == "groq"
    assert result.text == "groq javob"


@pytest.mark.asyncio
async def test_cloudflare_fallback_after_groq_429():
    client = SimpleNamespace(
        request=AsyncMock(
            side_effect=[
                _response(429, {"error": "quota"}),
                _response(200, {"result": {"response": "cf javob"}}),
            ]
        )
    )
    router = FreeAIProviderRouter(
        _settings(
            GROQ_API_KEY="key",
            CLOUDFLARE_ACCOUNT_ID="account",
            CLOUDFLARE_AI_API_TOKEN="token",
        ),
        client,
    )

    result = await router.generate_text("salom")

    assert result.provider == "cloudflare"
    assert result.text == "cf javob"
    assert router.blocked_until["groq"] > 0


@pytest.mark.asyncio
async def test_groq_whisper_is_primary():
    client = SimpleNamespace(
        request=AsyncMock(return_value=_response(200, {"text": "audio matni"}))
    )
    router = FreeAIProviderRouter(_settings(GROQ_API_KEY="key"), client)

    result = await router.transcribe_audio(b"audio", "audio/mpeg")

    assert result is not None
    assert result.provider == "groq"
    assert result.text == "audio matni"


@pytest.mark.asyncio
async def test_text_falls_back_from_groq_to_cloudflare_then_ollama():
    client = SimpleNamespace(
        request=AsyncMock(
            side_effect=[
                _response(429, {"error": "quota"}),
                _response(429, {"error": "quota"}),
                _response(200, {"response": "lokal javob"}),
            ]
        )
    )
    router = FreeAIProviderRouter(
        _settings(
            GROQ_API_KEY="key",
            CLOUDFLARE_ACCOUNT_ID="account",
            CLOUDFLARE_AI_API_TOKEN="token",
            OLLAMA_BASE_URL="http://localhost:11434/api",
        ),
        client,
    )

    result = await router.generate_text("salom")

    assert result.provider == "ollama"
    assert result.text == "lokal javob"


@pytest.mark.asyncio
async def test_audio_falls_back_from_groq_to_cloudflare():
    client = SimpleNamespace(
        request=AsyncMock(
            side_effect=[
                _response(429, {"error": "quota"}),
                _response(200, {"result": {"text": "cloudflare audio"}}),
            ]
        )
    )
    router = FreeAIProviderRouter(
        _settings(
            GROQ_API_KEY="key",
            CLOUDFLARE_ACCOUNT_ID="account",
            CLOUDFLARE_AI_API_TOKEN="token",
        ),
        client,
    )

    result = await router.transcribe_audio(b"audio", "audio/mpeg")

    assert result is not None
    assert result.provider == "cloudflare"
    assert result.text == "cloudflare audio"
