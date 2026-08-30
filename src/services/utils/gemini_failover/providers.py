"""
Non-Gemini provider integrations (Groq, Cerebras, Together AI, NVIDIA NIM, Cloudflare, etc.).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple

from src.services.utils.gemini_failover.models import (
    _FallbackResponse,
    _pause_provider,
    _provider_cooling_down,
)

logger = logging.getLogger(__name__)


def _extract_messages_from_contents(
    contents: Any,
    config: Any = None,
) -> tuple[list[dict[str, str]], Optional[str]]:
    system_instruction: Optional[str] = None
    if config is not None:
        si = getattr(config, "system_instruction", None)
        if si:
            system_instruction = str(si)

    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    if isinstance(contents, str):
        messages.append({"role": "user", "content": contents})
    elif isinstance(contents, (list, tuple)):
        for item in contents:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
            elif hasattr(item, "text"):
                messages.append({"role": "user", "content": str(item.text)})
            elif hasattr(item, "parts"):
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


def _get_secret(key_attr: str) -> str:
    try:
        from src.settings import settings as _settings
        val = getattr(_settings, key_attr, None)
        if val is not None:
            getter = getattr(val, "get_secret_value", None)
            if callable(getter):
                return getter() or ""
            return str(val or "")
    except Exception as exc:
        logger.debug("[AI_FALLBACK] Secret load %s: %s", key_attr, exc)
    return os.getenv(key_attr, "")


def _get_setting(attr: str, default: str = "") -> str:
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
        err_text = str(exc).lower()
        if any(x in err_text for x in ("429", "quota", "rate", "limit")):
            _pause_provider(provider_name, 900)
        else:
            _pause_provider(provider_name, 60)
    return None


async def _call_cloudflare(
    messages: list[dict[str, str]],
) -> Optional[_FallbackResponse]:
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


_NON_GEMINI_PROVIDERS = [
    ("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_TEXT_MODEL"),
    ("cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", "CEREBRAS_MODEL"),
    ("togetherai", "TOGETHERAI_API_KEY", "https://api.together.xyz/v1", "TOGETHERAI_MODEL"),
    ("nvidia_nim", "NVIDIA_NIM_API_KEY", "https://integrate.api.nvidia.com/v1", "NVIDIA_NIM_MODEL"),
    ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "OPENROUTER_TEXT_MODEL"),
    ("huggingface", "HUGGINGFACE_API_KEY", None, "HUGGINGFACE_MODEL"),
    ("cloudflare", "CLOUDFLARE_AI_API_TOKEN", None, "CLOUDFLARE_TEXT_MODEL"),
]


async def _non_gemini_fallback(
    contents: Any,
    config: Any = None,
    log_prefix: str = "[GEMINI]",
) -> Optional[Tuple[Any, str]]:
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
