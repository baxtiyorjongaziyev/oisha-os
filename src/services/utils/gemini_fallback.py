"""Gemini model failover + multi-provider fallback for production AI pipelines.

When all Gemini models are in quota cooldown, automatically falls back to
free providers: Groq → Cerebras → Together AI → NVIDIA NIM → OpenRouter →
Hugging Face → Cloudflare Workers AI.
"""

from __future__ import annotations

import inspect
import logging
import os
import time
from typing import Any, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
)

_MODEL_QUOTA_BLOCKED_UNTIL: dict[str, float] = {}

# Provider-level cooldown (shared with non-Gemini providers)
_PROVIDER_BLOCKED_UNTIL: dict[str, float] = {}


class GeminiModelCooldownError(RuntimeError):
    """Raised when every configured Gemini model is paused after quota errors."""


def _quota_cooldown_seconds(error: Exception) -> int:
    text = str(error).lower()
    if "perday" in text or "per day" in text:
        return int(os.getenv("GEMINI_DAILY_QUOTA_COOLDOWN_SECONDS", "21600"))
    return int(os.getenv("GEMINI_MODEL_QUOTA_COOLDOWN_SECONDS", "300"))


def _pause_model_for_quota(model: str, error: Exception) -> None:
    cooldown_seconds = _quota_cooldown_seconds(error)
    _MODEL_QUOTA_BLOCKED_UNTIL[model] = max(
        _MODEL_QUOTA_BLOCKED_UNTIL.get(model, 0.0),
        time.monotonic() + cooldown_seconds,
    )
    logger.warning(
        "[GEMINI] model=%s quota cooldown active for %ss",
        model,
        cooldown_seconds,
    )


def _model_quota_cooling_down(model: str) -> bool:
    blocked_until = _MODEL_QUOTA_BLOCKED_UNTIL.get(model, 0.0)
    if blocked_until <= time.monotonic():
        _MODEL_QUOTA_BLOCKED_UNTIL.pop(model, None)
        return False
    return True


def _pause_provider(provider: str, seconds: int) -> None:
    _PROVIDER_BLOCKED_UNTIL[provider] = max(
        _PROVIDER_BLOCKED_UNTIL.get(provider, 0.0),
        time.monotonic() + seconds,
    )


def _provider_cooling_down(provider: str) -> bool:
    blocked_until = _PROVIDER_BLOCKED_UNTIL.get(provider, 0.0)
    if blocked_until <= time.monotonic():
        _PROVIDER_BLOCKED_UNTIL.pop(provider, None)
        return False
    return True


def reset_model_quota_cooldowns() -> None:
    """Clear process-local quota state. Intended for tests and controlled reloads."""
    _MODEL_QUOTA_BLOCKED_UNTIL.clear()
    _PROVIDER_BLOCKED_UNTIL.clear()


def is_quota_error(error: Exception) -> bool:
    text = str(error).lower()
    return "429" in text or "resource_exhausted" in text or "quota" in text


def is_transient_error(error: Exception) -> bool:
    text = str(error).lower()
    return is_quota_error(error) or any(
        marker in text
        for marker in (
            "503",
            "unavailable",
            "high demand",
            "temporarily",
            "timeout",
            "deadline_exceeded",
            "internal",
        )
    )


def model_candidates(
    primary_model: str,
    *,
    env_name: Optional[str] = None,
    extra_models: Iterable[str] = DEFAULT_FALLBACK_MODELS,
) -> List[str]:
    configured = os.getenv(env_name or "", "") if env_name else ""
    common = os.getenv("GEMINI_FALLBACK_MODELS", "")
    raw_models = [primary_model]
    raw_models.extend(configured.split(",") if configured else [])
    raw_models.extend(common.split(",") if common else [])
    raw_models.extend(extra_models)

    result: List[str] = []
    for raw_model in raw_models:
        model = str(raw_model or "").strip()
        if model.startswith("models/"):
            model = model.removeprefix("models/")
        if model and model not in result:
            result.append(model)
    return result


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


# ---------------------------------------------------------------------------
# Gemini-compatible response wrapper for non-Gemini providers
# ---------------------------------------------------------------------------

class _FallbackResponse:
    """Minimal Gemini-compatible response object wrapping plain text."""

    def __init__(self, text: str, provider: str, model: str):
        self.text = text
        self._provider = provider
        self._model = model
        # Mimic Gemini response structure for consumers that access .candidates
        self.candidates = [_FallbackCandidate(text)]

    def __str__(self) -> str:
        return self.text


class _FallbackCandidate:
    def __init__(self, text: str):
        self.content = _FallbackContent(text)
        self.finish_reason = "STOP"


class _FallbackContent:
    def __init__(self, text: str):
        self.parts = [_FallbackPart(text)]
        self.role = "model"


class _FallbackPart:
    def __init__(self, text: str):
        self.text = text


# ---------------------------------------------------------------------------
# Helper to extract text from Gemini-format contents for non-Gemini providers
# ---------------------------------------------------------------------------

def _extract_messages_from_contents(
    contents: Any,
    config: Any = None,
) -> tuple[list[dict[str, str]], Optional[str]]:
    """Convert Gemini SDK contents/config into OpenAI-style messages list.

    Returns (messages, system_instruction).
    """
    system_instruction: Optional[str] = None
    if config is not None:
        si = getattr(config, "system_instruction", None)
        if si:
            system_instruction = str(si)

    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # contents can be: str, list[str], list[Part], list[Content], etc.
    if isinstance(contents, str):
        messages.append({"role": "user", "content": contents})
    elif isinstance(contents, (list, tuple)):
        for item in contents:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
            elif hasattr(item, "text"):
                # google.genai Part object
                messages.append({"role": "user", "content": str(item.text)})
            elif hasattr(item, "parts"):
                # google.genai Content object
                role = getattr(item, "role", "user") or "user"
                role = "assistant" if role == "model" else role
                parts_text = []
                for part in item.parts:
                    if hasattr(part, "text") and part.text:
                        parts_text.append(str(part.text))
                if parts_text:
                    messages.append({"role": role, "content": "\n".join(parts_text)})
            else:
                messages.append({"role": "user", "content": str(item)})
    else:
        messages.append({"role": "user", "content": str(contents)})

    return messages, system_instruction


# ---------------------------------------------------------------------------
# Non-Gemini provider implementations (OpenAI-compatible + Cloudflare)
# ---------------------------------------------------------------------------

def _get_secret(key_attr: str) -> str:
    """Safely extract API key from settings or env."""
    try:
        from src.settings import settings as _settings
        val = getattr(_settings, key_attr, None)
        if val is not None:
            getter = getattr(val, "get_secret_value", None)
            if callable(getter):
                return getter() or ""
            return str(val or "")
    except Exception:
        pass
    return os.getenv(key_attr, "")


def _get_setting(attr: str, default: str = "") -> str:
    """Get a non-secret setting value."""
    try:
        from src.settings import settings as _settings
        return str(getattr(_settings, attr, default) or default)
    except Exception:
        return os.getenv(attr, default)


async def _call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2048,
    provider_name: str,
) -> Optional[_FallbackResponse]:
    """Call any OpenAI-compatible API endpoint."""
    if not api_key:
        return None
    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=45) as http:
            resp = await http.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            text = msg.get("content") or msg.get("reasoning") or ""
            if text:
                logger.info("[AI_FALLBACK] %s muvaffaqiyatli (model=%s)", provider_name, model)
                return _FallbackResponse(text.strip(), provider_name, model)
    except Exception as exc:
        logger.warning("[AI_FALLBACK] %s xato: %s", provider_name, exc)
        # Determine cooldown duration
        err_text = str(exc).lower()
        if any(x in err_text for x in ("429", "quota", "rate", "limit")):
            _pause_provider(provider_name, 900)
        else:
            _pause_provider(provider_name, 60)
    return None


async def _call_cloudflare(
    messages: list[dict[str, str]],
) -> Optional[_FallbackResponse]:
    """Cloudflare Workers AI — custom API format, not OpenAI-compatible."""
    account_id = _get_setting("CLOUDFLARE_ACCOUNT_ID")
    api_token = _get_secret("CLOUDFLARE_AI_API_TOKEN")
    model = _get_setting("CLOUDFLARE_TEXT_MODEL", "@cf/meta/llama-3.1-8b-instruct")
    if not account_id or not api_token:
        return None
    try:
        import httpx
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(url, json={"messages": messages}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("result", {}).get("response", "")
            if text:
                logger.info("[AI_FALLBACK] Cloudflare muvaffaqiyatli (model=%s)", model)
                return _FallbackResponse(text.strip(), "cloudflare", model)
    except Exception as exc:
        logger.warning("[AI_FALLBACK] Cloudflare xato: %s", exc)
        err_text = str(exc).lower()
        if any(x in err_text for x in ("429", "quota", "rate")):
            _pause_provider("cloudflare", 900)
        else:
            _pause_provider("cloudflare", 60)
    return None


# ---------------------------------------------------------------------------
# Provider registry — ordered by speed and free quota generosity
# ---------------------------------------------------------------------------

_NON_GEMINI_PROVIDERS = [
    # (provider_name, api_key_attr, base_url, model_attr)
    ("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_TEXT_MODEL"),
    ("cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", "CEREBRAS_MODEL"),
    ("togetherai", "TOGETHERAI_API_KEY", "https://api.together.xyz/v1", "TOGETHERAI_MODEL"),
    ("nvidia_nim", "NVIDIA_NIM_API_KEY", "https://integrate.api.nvidia.com/v1", "NVIDIA_NIM_MODEL"),
    ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "OPENROUTER_TEXT_MODEL"),
    ("huggingface", "HUGGINGFACE_API_KEY", None, "HUGGINGFACE_MODEL"),  # Special base_url
    ("cloudflare", "CLOUDFLARE_AI_API_TOKEN", None, "CLOUDFLARE_TEXT_MODEL"),  # Custom API
]


async def _non_gemini_fallback(
    contents: Any,
    config: Any = None,
    log_prefix: str = "[GEMINI]",
) -> Optional[Tuple[Any, str]]:
    """Try non-Gemini providers when all Gemini models are exhausted.

    Returns (response, provider_name) or None if all providers fail.
    """
    messages, _ = _extract_messages_from_contents(contents, config)
    if not messages:
        return None

    for provider_name, key_attr, base_url, model_attr in _NON_GEMINI_PROVIDERS:
        if _provider_cooling_down(provider_name):
            logger.debug(
                "%s provider=%s cooling down; skipping",
                log_prefix,
                provider_name,
            )
            continue

        api_key = _get_secret(key_attr)
        model = _get_setting(model_attr, "")
        if not api_key or not model:
            continue

        # Cloudflare has a custom API, not OpenAI-compatible
        if provider_name == "cloudflare":
            result = await _call_cloudflare(messages)
            if result is not None:
                logger.warning(
                    "%s Gemini kvotasi tugadi → %s bilan javob berildi",
                    log_prefix,
                    provider_name,
                )
                return result, provider_name
            continue

        # Hugging Face has a special base URL format
        if provider_name == "huggingface":
            base_url = f"https://api-inference.huggingface.co/models/{model}/v1"

        result = await _call_openai_compatible(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=messages,
            provider_name=provider_name,
        )
        if result is not None:
            logger.warning(
                "%s Gemini kvotasi tugadi → %s bilan javob berildi",
                log_prefix,
                provider_name,
            )
            return result, provider_name

    return None


# ---------------------------------------------------------------------------
# Main entry point — used by 17+ production files
# ---------------------------------------------------------------------------

async def generate_content_with_fallback(
    client: Any,
    *,
    primary_model: str,
    contents: Any,
    config: Any = None,
    env_name: Optional[str] = None,
    log_prefix: str = "[GEMINI]",
) -> Tuple[Any, str]:
    """Generate content with Gemini model failover + multi-provider fallback.

    1. Tries all configured Gemini models (primary + fallbacks)
    2. If all Gemini models are in quota cooldown, falls back to non-Gemini
       providers: Groq → Cerebras → Together AI → NVIDIA NIM → OpenRouter →
       Hugging Face → Cloudflare
    """
    aio_models = getattr(getattr(client, "aio", None), "models", None)
    models = aio_models or getattr(client, "models", None)
    if not models:
        raise RuntimeError("Gemini models API is not available")

    last_error: Optional[Exception] = None
    candidates = model_candidates(primary_model, env_name=env_name)
    attempted_models = 0
    for model in candidates:
        if _model_quota_cooling_down(model):
            logger.info("%s model=%s quota cooldown active; skipping", log_prefix, model)
            continue

        attempted_models += 1
        kwargs = {"model": model, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        try:
            response = await _maybe_await(models.generate_content(**kwargs))
            if model != primary_model:
                logger.warning("%s recovered with fallback model=%s", log_prefix, model)
            return response, model
        except Exception as exc:
            last_error = exc
            if is_quota_error(exc):
                _pause_model_for_quota(model, exc)
            if not is_transient_error(exc):
                raise
            logger.warning(
                "%s model=%s unavailable (%s); trying fallback",
                log_prefix,
                model,
                type(exc).__name__,
            )

    # All Gemini models exhausted — try non-Gemini providers
    logger.warning(
        "%s Barcha Gemini modellar cooldown — non-Gemini fallback boshlanmoqda...",
        log_prefix,
    )
    fallback_result = await _non_gemini_fallback(contents, config, log_prefix)
    if fallback_result is not None:
        return fallback_result

    if not attempted_models:
        raise GeminiModelCooldownError(
            "All configured Gemini models are cooling down and no fallback provider available"
        )
    raise last_error or RuntimeError("Gemini generation failed and no fallback available")
