"""AI provider smoke tests.

- Gemini: RUN_LIVE_TESTS=1 kerak (quota 429 bo'lishi mumkin)
- Groq/Cerebras: Avtomatik — kalitlar bo'lsa ishlaydi
- OpenRouter/Cloudflare: RUN_LIVE_TESTS=1 yoki kalit bo'lsa
"""

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_LIVE") == "1",
    reason="Live provider tests disabled by SKIP_LIVE=1.",
)


# ---------------------------------------------------------------------------
# Gemini (quota 429 bo'lishi mumkin — faqat ixtiyoriy)
# ---------------------------------------------------------------------------

pytestmark_gemini = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live Gemini test; set RUN_LIVE_TESTS=1.",
)


@pytestmark_gemini
def test_gemini_generate_content_live():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key, "GEMINI_API_KEY is required"

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Salom, 2-3 sozda javob bering.",
    )
    assert response.text
    print(f"[Gemini] OK: {response.text[:80]}")


# ---------------------------------------------------------------------------
# Groq — avtomatik (kalit bo'lsa ishlaydi)
# ---------------------------------------------------------------------------

def _get_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        from src.settings import settings
        return settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else ""
    except Exception:
        return ""


def test_groq_live():
    pytest.importorskip("openai")
    api_key = _get_groq_key()
    if not api_key:
        pytest.skip("GROQ_API_KEY not configured")

    import openai
    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Say hello in 3 words."}],
        max_tokens=50,
    )
    text = response.choices[0].message.content
    assert text
    print(f"[Groq] OK: {text[:80]}")


# ---------------------------------------------------------------------------
# Cerebras — avtomatik (kalit bo'lsa ishlaydi)
# ---------------------------------------------------------------------------

def _get_cerebras_key():
    key = os.getenv("CEREBRAS_API_KEY")
    if key:
        return key
    try:
        from src.settings import settings
        return settings.CEREBRAS_API_KEY.get_secret_value() if settings.CEREBRAS_API_KEY else ""
    except Exception:
        return ""


def test_cerebras_live():
    pytest.importorskip("openai")
    api_key = _get_cerebras_key()
    if not api_key:
        pytest.skip("CEREBRAS_API_KEY not configured")

    import openai
    client = openai.OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")
    response = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": "Say hello in 3 words."}],
        max_tokens=50,
    )
    msg = response.choices[0].message
    text = msg.content or getattr(msg, "reasoning", None)
    assert text
    print(f"[Cerebras] OK: {text[:80]}")


# ---------------------------------------------------------------------------
# OpenRouter — RUN_LIVE_TESTS=1 yoki kalit bo'lsa
# ---------------------------------------------------------------------------

def _get_openrouter_key():
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        from src.settings import settings
        return settings.OPENROUTER_API_KEY.get_secret_value() if settings.OPENROUTER_API_KEY else ""
    except Exception:
        return ""


def test_openrouter_live():
    if os.getenv("SKIP_LIVE") == "1":
        pytest.skip("Live provider tests disabled by SKIP_LIVE=1")
    pytest.importorskip("openai")
    api_key = _get_openrouter_key()
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not configured")

    import openai
    client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    response = client.chat.completions.create(
        model="meta-llama/llama-3.2-3b-instruct",
        messages=[{"role": "user", "content": "Say hello in 3 words."}],
        max_tokens=50,
        timeout=60,
    )
    text = response.choices[0].message.content
    assert text
    print(f"[OpenRouter] OK: {text[:80]}")


# ---------------------------------------------------------------------------
# Cloudflare Workers AI — RUN_LIVE_TESTS=1 yoki kalit bo'lsa
# ---------------------------------------------------------------------------

def test_cloudflare_live():
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_AI_API_TOKEN")
    if not account_id or not api_token:
        try:
            from src.settings import settings
            account_id = account_id or settings.CLOUDFLARE_ACCOUNT_ID or ""
            api_token = api_token or (settings.CLOUDFLARE_AI_API_TOKEN.get_secret_value() if settings.CLOUDFLARE_AI_API_TOKEN else "")
        except Exception:
            pass
    if not account_id or not api_token:
        pytest.skip("CLOUDFLARE credentials not configured")

    import httpx
    model = "@cf/meta/llama-3.1-8b-instruct"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    resp = httpx.post(url, json={"messages": [{"role": "user", "content": "Say hello in 3 words."}]}, headers=headers, timeout=30)
    resp.raise_for_status()
    text = resp.json().get("result", {}).get("response", "")
    assert text
    print(f"[Cloudflare] OK: {text[:80]}")


# ---------------------------------------------------------------------------
# Fallback chain test — Gemini blocked → Groq/Cerebras ishlaydi
# ---------------------------------------------------------------------------

def test_fallback_chain_end_to_end():
    """Gemini → Groq → Cerebras chain ishlayaptimi?"""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from src.services.utils.gemini_fallback import generate_content_with_fallback, reset_model_quota_cooldowns

    reset_model_quota_cooldowns()

    # Gemini barcha modellarni block qiladi
    models = SimpleNamespace(
        generate_content=AsyncMock(
            side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
        )
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    async def run():
        response, provider = await generate_content_with_fallback(
            client,
            primary_model="gemini-2.5-flash",
            contents="Test",
            log_prefix="[TEST]",
        )
        return response, provider

    has_groq = bool(_get_groq_key())
    has_cerebras = bool(_get_cerebras_key())

    if has_groq or has_cerebras:
        response, provider = asyncio.run(run())
        assert response is not None
        print(f"[Fallback] OK — provider: {provider}")
    else:
        pytest.skip("No fallback API keys configured")
