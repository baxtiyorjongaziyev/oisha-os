"""
Core AI Router execution and provider fallback engine.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
import time
from typing import Any, Dict, Optional

import structlog
from src.context import app_ctx
from src.agents.router_pkg.models_cost import (
    MODEL_CATALOG,
    TASK_TO_TIER,
    TaskType,
    _COMPLEX_FALLBACK_PROVIDERS,
    _SIMPLE_TASK_PROVIDERS,
    _cache_get,
    _cache_put,
    _error_result,
    _estimate_cost,
    _log_usage,
    _maybe_degrade_tier,
)

logger = structlog.get_logger()

app_ctx.gemini_client = None


def _get_gemini_client() -> Optional[Any]:
    if app_ctx.gemini_client is not None:
        return app_ctx.gemini_client
    try:
        from google import genai
    except ImportError:
        logger.error("[AI_ROUTER] google-genai not installed.")
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            from src import config

            api_key = getattr(config, "GEMINI_API_KEY", "")
        except Exception:
            pass
    if not api_key:
        logger.error("[AI_ROUTER] GEMINI_API_KEY not set")
        return None
    app_ctx.gemini_client = genai.Client(api_key=api_key)
    return app_ctx.gemini_client


def _resolve_gemini_client() -> Optional[Any]:
    import sys
    facade = sys.modules.get("src.agents.ai_router")
    getter = getattr(facade, "_get_gemini_client", _get_gemini_client) if facade else _get_gemini_client
    if callable(getter):
        return getter()
    return getter


async def _call_gemini(
    client: Any,
    model: str,
    prompt: str,
    system: Optional[str],
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    from google.genai import types

    config_args: Dict[str, Any] = {
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if system:
        config_args["system_instruction"] = system

    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(**config_args),
    )
    text = (response.text or "").strip()
    usage = getattr(response, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) or 0
    tokens_out = getattr(usage, "candidates_token_count", 0) or 0
    return {"text": text, "tokens_in": int(tokens_in), "tokens_out": int(tokens_out)}


async def _route_simple(prompt: str, system: Optional[str], max_tokens: int, temperature: float, tier: str, prompt_hash: str, start: float, task_type: str, user_id: Optional[int], context: Optional[Dict[str, Any]], model_name: str) -> Dict[str, Any]:
    try:
        from src.services.utils.free_ai_router import get_free_ai_router

        routed = await get_free_ai_router().generate_text(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature, providers=_SIMPLE_TASK_PROVIDERS
        )
        final = {
            "text": routed.text, "model": routed.model, "provider": routed.provider, "tier": tier,
            "tokens_in": routed.tokens_in, "tokens_out": routed.tokens_out, "cost_usd": 0.0,
            "latency_ms": int((time.time() - start) * 1000), "success": True, "error": None,
            "cached": False, "prompt_hash": prompt_hash,
        }
        _cache_put(prompt_hash, final)
        return final
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return _error_result(str(exc), task_type=task_type, tier=tier, model=model_name, prompt_hash=prompt_hash, start=start, user_id=user_id, context=context)


def _facade_getattr(name: str, default: Any) -> Any:
    import sys
    facade = sys.modules.get("src.agents.ai_router")
    return getattr(facade, name, default) if facade else default


async def route(
    prompt: str,
    task_type: TaskType = "draft",
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    max_tokens: Optional[int] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    bypass_cache: bool = False,
) -> Dict[str, Any]:
    """Markazlashgan AI chaqiruvi."""
    start = time.time()
    base_tier = TASK_TO_TIER.get(task_type, "L1")
    degrade_fn = _facade_getattr("_maybe_degrade_tier", _maybe_degrade_tier)
    tier = await degrade_fn(base_tier)
    tier_cfg = MODEL_CATALOG[tier]
    model_name = tier_cfg["model"]
    if max_tokens is None:
        max_tokens = tier_cfg["max_tokens_default"]

    hash_payload = f"{task_type}|{tier}|{system or ''}|{prompt}"
    prompt_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()[:16]

    if not bypass_cache:
        cached = _cache_get(prompt_hash)
        if cached:
            cached_copy = dict(cached)
            cached_copy["cached"] = True
            cached_copy["latency_ms"] = int((time.time() - start) * 1000)
            return cached_copy

    if task_type in {"draft", "classify", "summarize"}:
        return await _route_simple(prompt, system, max_tokens, temperature, tier, prompt_hash, start, task_type, user_id, context, model_name)

    client = _resolve_gemini_client()
    if client is None:
        return await _route_simple(prompt, system, max_tokens, temperature, tier, prompt_hash, start, task_type, user_id, context, model_name)

    last_error: Optional[str] = None
    call_gemini_fn = _facade_getattr("_call_gemini", _call_gemini)
    sleep_fn = getattr(_facade_getattr("asyncio", asyncio), "sleep", asyncio.sleep)
    for attempt_tier in [tier]:
        attempt_cfg = MODEL_CATALOG[attempt_tier]
        attempt_model = attempt_cfg["model"]
        try:
            result = await call_gemini_fn(client=client, model=attempt_model, prompt=prompt, system=system, max_tokens=max_tokens, temperature=temperature)
            cost = _estimate_cost(attempt_tier, result["tokens_in"], result["tokens_out"])
            final = {
                "text": result["text"], "model": attempt_model, "tier": attempt_tier, "tokens_in": result["tokens_in"],
                "tokens_out": result["tokens_out"], "cost_usd": cost, "latency_ms": int((time.time() - start) * 1000),
                "success": True, "error": None, "cached": False, "prompt_hash": prompt_hash,
            }
            _cache_put(prompt_hash, final)
            await _log_usage(task_type=task_type, tier=attempt_tier, model=attempt_model, prompt_hash=prompt_hash, prompt_preview=prompt[:200], response_preview=result["text"][:200], tokens_in=result["tokens_in"], tokens_out=result["tokens_out"], cost_usd=cost, latency_ms=final["latency_ms"], user_id=user_id, context=context, success=True, error=None)
            return final
        except Exception as e:
            last_error = str(e)
            logger.warning("[AI_ROUTER] Tier %s (%s) failed: %s", attempt_tier, attempt_model, e)
            await sleep_fn(0.5 + random.random())

    try:
        from src.services.utils.free_ai_router import get_free_ai_router

        routed = await get_free_ai_router().generate_text(prompt, system=system, max_tokens=max_tokens, temperature=temperature, providers=_COMPLEX_FALLBACK_PROVIDERS)
        final = {
            "text": routed.text, "model": routed.model, "provider": routed.provider, "tier": tier, "tokens_in": routed.tokens_in,
            "tokens_out": routed.tokens_out, "cost_usd": 0.0, "latency_ms": int((time.time() - start) * 1000), "success": True,
            "error": None, "cached": False, "prompt_hash": prompt_hash,
        }
        _cache_put(prompt_hash, final)
        return final
    except Exception as fallback_exc:
        last_error = last_error or str(fallback_exc)

    return _error_result(last_error or "All tiers failed", task_type=task_type, tier=tier, model=model_name, prompt_hash=prompt_hash, start=start, user_id=user_id, context=context)
