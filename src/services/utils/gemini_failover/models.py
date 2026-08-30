"""
Constants, response wrappers and error helpers for Gemini fallback.
"""
from __future__ import annotations

import inspect
import os
import time
from typing import Any, Iterable, List, Optional

DEFAULT_FALLBACK_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
)

_MODEL_QUOTA_BLOCKED_UNTIL: dict[str, float] = {}
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


class _FallbackResponse:
    def __init__(self, text: str, provider: str, model: str):
        self.text = text
        self._provider = provider
        self._model = model
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
