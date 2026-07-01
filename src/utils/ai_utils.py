"""Global AI utility with full multi-provider fallback chain.

Gemini → Groq → Cerebras → Together AI → NVIDIA NIM → OpenRouter →
Hugging Face → Cloudflare Workers AI.
"""

import logging

from src.settings import settings
from src.services.utils.gemini_fallback import (
    generate_content_with_fallback,
    is_transient_error,
    _get_secret,
    _get_setting,
    _call_openai_compatible,
    _call_cloudflare,
    _extract_messages_from_contents,
    _provider_cooling_down,
    _FallbackResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider chain for safe_ai_call — same order as gemini_fallback.py
# ---------------------------------------------------------------------------

_PROVIDER_CHAIN = [
    # (provider_name, api_key_attr, base_url, model_attr)
    ("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_TEXT_MODEL"),
    ("cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", "CEREBRAS_MODEL"),
    ("togetherai", "TOGETHERAI_API_KEY", "https://api.together.xyz/v1", "TOGETHERAI_MODEL"),
    ("nvidia_nim", "NVIDIA_NIM_API_KEY", "https://integrate.api.nvidia.com/v1", "NVIDIA_NIM_MODEL"),
    ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "OPENROUTER_TEXT_MODEL"),
    ("huggingface", "HUGGINGFACE_API_KEY", None, "HUGGINGFACE_MODEL"),
    ("cloudflare", "CLOUDFLARE_AI_API_TOKEN", None, "CLOUDFLARE_TEXT_MODEL"),
]


def _make_response(text: str):
    """Wrap text in a simple object that mimics Gemini response."""
    return _FallbackResponse(text, "fallback", "unknown")


async def _try_all_providers(prompt, system_instruction=None):
    """Try all non-Gemini providers in priority order."""
    # Build OpenAI-style messages
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": str(system_instruction)})

    user_content = str(prompt[0]) if isinstance(prompt, list) else str(prompt)
    messages.append({"role": "user", "content": user_content})

    for provider_name, key_attr, base_url, model_attr in _PROVIDER_CHAIN:
        if _provider_cooling_down(provider_name):
            continue

        api_key = _get_secret(key_attr)
        model = _get_setting(model_attr, "")
        if not api_key or not model:
            continue

        # Cloudflare — custom API
        if provider_name == "cloudflare":
            result = await _call_cloudflare(messages)
            if result is not None:
                return result
            continue

        # Hugging Face — special base URL
        actual_base_url = base_url
        if provider_name == "huggingface":
            actual_base_url = f"https://api-inference.huggingface.co/models/{model}/v1"

        result = await _call_openai_compatible(
            api_key=api_key,
            base_url=actual_base_url,
            model=model,
            messages=messages,
            provider_name=provider_name,
        )
        if result is not None:
            return result

    return None


async def safe_ai_call(
    client,
    prompt,
    system_instruction=None,
    model=None,
    mime_type=None,
    retries=3,
):
    """Global utility with Gemini + 7 free provider fallback chain.

    Fallback order:
    1. Gemini (primary + fallback models)
    2. Groq (eng tez, 300+ TPS)
    3. Cerebras (1M tokens/day)
    4. Together AI ($1 credit)
    5. NVIDIA NIM (1000 free credits)
    6. OpenRouter (50+ free models)
    7. Hugging Face (rate-limited)
    8. Cloudflare Workers AI (10K neurons/day)
    """
    from google.genai import types

    model = model or settings.GEMINI_CALL_MODEL
    config = types.GenerateContentConfig(
        system_instruction=system_instruction, response_mime_type=mime_type
    )

    # 1. Try Gemini with fallback models (includes built-in non-Gemini fallback)
    try:
        response, _ = await generate_content_with_fallback(
            client,
            primary_model=model,
            contents=prompt,
            config=config,
            env_name="GEMINI_GLOBAL_FALLBACK_MODELS",
            log_prefix="[GLOBAL AI]",
        )
        return response
    except Exception as exc:
        if not is_transient_error(exc):
            raise
        logger.warning("[GLOBAL AI] Gemini va built-in fallback ham ishlamadi; alohida providerlarni sinab ko'rish...")

    # 2. Direct provider fallback (agar gemini_fallback ichidagi ham ishlamagan bo'lsa)
    result = await _try_all_providers(prompt, system_instruction)
    if result is not None:
        return result

    logger.warning("[GLOBAL AI] Barcha providerlar ishlamadi.")
    return None
