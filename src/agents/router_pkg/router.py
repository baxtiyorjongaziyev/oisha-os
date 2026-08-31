"""
Core AI Router dispatch engine.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from typing import Any, Dict, Literal, Optional

import structlog

from src.agents.router_pkg.models_cost import (
    MODEL_TIERS,
    TASK_TO_TIER,
    TaskType,
    _cache_get,
    _cache_put,
    _error_result,
    _estimate_cost,
    _get_gemini_client,
    _log_usage,
    _maybe_degrade_tier,
)
from src.services.utils.gemini_fallback import generate_content_with_fallback

logger = structlog.get_logger()


async def _call_gemini(
    prompt: str,
    model: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    text = await generate_content_with_fallback(
        prompt=full_prompt,
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    tokens_in = len(full_prompt.split()) * 2
    tokens_out = len(text.split()) * 2
    return {"text": text, "tokens_in": tokens_in, "tokens_out": tokens_out}


async def route(
    prompt: str,
    task_type: TaskType = "draft",
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    use_cache: bool = True,
    preferred_tier: Optional[str] = None,
) -> Dict[str, Any]:
    start_time = time.time()
    ctx = context or {}

    prompt_hash = hashlib.sha256(f"{task_type}:{prompt}:{system_prompt}".encode()).hexdigest()
    if use_cache:
        cached = _cache_get(prompt_hash)
        if cached:
            cached_copy = dict(cached)
            cached_copy["cached"] = True
            return cached_copy

    tier = preferred_tier or TASK_TO_TIER.get(task_type, "L1")
    tier = await _maybe_degrade_tier(tier)
    model = MODEL_TIERS.get(tier, "gemini-1.5-flash")

    last_exc = None
    for attempt in range(3):
        try:
            res = await _call_gemini(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = _estimate_cost(tier, res["tokens_in"], res["tokens_out"])

            result = {
                "text": res["text"],
                "model": model,
                "tier": tier,
                "task_type": task_type,
                "tokens_in": res["tokens_in"],
                "tokens_out": res["tokens_out"],
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "success": True,
                "cached": False,
                "error": None,
            }

            if use_cache and result["text"]:
                _cache_put(prompt_hash, result)

            asyncio.create_task(
                _log_usage(
                    task_type=task_type,
                    tier=tier,
                    model=model,
                    tokens_in=res["tokens_in"],
                    tokens_out=res["tokens_out"],
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    success=True,
                    user_id=user_id,
                    lead_id=lead_id or ctx.get("lead_id"),
                )
            )

            return result

        except Exception as exc:
            last_exc = exc
            await asyncio.sleep(0.5 * (attempt + 1))

    latency_ms = int((time.time() - start_time) * 1000)
    err_str = str(last_exc) if last_exc else "Unknown AI Router Error"
    logger.error("AI Router routing failed", task_type=task_type, error=err_str)

    asyncio.create_task(
        _log_usage(
            task_type=task_type,
            tier=tier,
            model=model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=latency_ms,
            success=False,
            user_id=user_id,
            lead_id=lead_id or ctx.get("lead_id"),
            error=err_str,
        )
    )

    return _error_result(err_str, task_type, tier, latency_ms)
