"""Small Gemini model failover helpers shared by production AI pipelines."""

from __future__ import annotations

import inspect
import logging
import os
from typing import Any, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
)


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
    for index, model in enumerate(candidates):
        kwargs = {"model": model, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        try:
            response = await _maybe_await(models.generate_content(**kwargs))
            if index:
                logger.warning("%s recovered with fallback model=%s", log_prefix, model)
            return response, model
        except Exception as exc:
            last_error = exc
            if not is_transient_error(exc) or index == len(candidates) - 1:
                raise
            logger.warning(
                "%s model=%s unavailable (%s); trying fallback",
                log_prefix,
                model,
                type(exc).__name__,
            )

    raise last_error or RuntimeError("Gemini generation failed")
