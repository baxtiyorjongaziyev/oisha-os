"""Small Gemini model failover helpers shared by production AI pipelines."""

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


def reset_model_quota_cooldowns() -> None:
    """Clear process-local quota state. Intended for tests and controlled reloads."""
    _MODEL_QUOTA_BLOCKED_UNTIL.clear()


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


async def generate_content_with_fallback(
    client: Any,
    *,
    primary_model: str,
    contents: Any,
    config: Any = None,
    env_name: Optional[str] = None,
    log_prefix: str = "[GEMINI]",
) -> Tuple[Any, str]:
    """Generate content with model failover for quota and temporary outages."""
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

    if not attempted_models:
        raise GeminiModelCooldownError(
            "All configured Gemini models are cooling down after quota exhaustion"
        )
    raise last_error or RuntimeError("Gemini generation failed")
