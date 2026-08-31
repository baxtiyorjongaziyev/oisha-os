"""
Core generate_content_with_fallback orchestrator.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from src.services.utils.gemini_failover.models import (
    GeminiModelCooldownError,
    _maybe_await,
    _model_quota_cooling_down,
    _pause_model_for_quota,
    is_quota_error,
    is_transient_error,
    model_candidates,
)
import src.services.utils.gemini_fallback as _facade

logger = logging.getLogger(__name__)


async def generate_content_with_fallback(
    client: Any,
    *,
    primary_model: str,
    contents: Any,
    config: Any = None,
    env_name: Optional[str] = None,
    log_prefix: str = "[GEMINI]",
) -> Tuple[Any, str]:
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

    logger.warning(
        "%s Barcha Gemini modellar cooldown — non-Gemini fallback boshlanmoqda...",
        log_prefix,
    )
    fallback_fn = getattr(_facade, "_non_gemini_fallback", None)
    fallback_result = None
    if callable(fallback_fn):
        fallback_result = await fallback_fn(contents, config, log_prefix)
    if fallback_result is not None:
        return fallback_result

    if not attempted_models:
        raise GeminiModelCooldownError(
            "All configured Gemini models are cooling down and no fallback provider available"
        )
    raise last_error or RuntimeError("Gemini generation failed and no fallback available")
