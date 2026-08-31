"""
Configuration, model tiers, caching and cost tracking for AI Router.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Literal, Optional

import structlog
from src.context import app_ctx
from src.settings import settings

logger = structlog.get_logger()

TaskType = Literal["draft", "classify", "summarize", "reason", "negotiate", "escalate"]

TASK_TO_TIER: Dict[str, str] = {
    "draft": "L1",
    "classify": "L1",
    "summarize": "L2",
    "reason": "L3",
    "negotiate": "L3",
    "escalate": "L4",
}

MODEL_TIERS: Dict[str, str] = {
    "L1": os.getenv("AI_ROUTER_L1_MODEL", "gemini-1.5-flash"),
    "L2": os.getenv("AI_ROUTER_L2_MODEL", "gemini-1.5-flash"),
    "L3": os.getenv("AI_ROUTER_L3_MODEL", "gemini-1.5-pro"),
    "L4": os.getenv("AI_ROUTER_L4_MODEL", "gemini-1.5-pro"),
}

TIER_COST_PER_1K: Dict[str, Dict[str, float]] = {
    "L1": {"input": 0.000075, "output": 0.0003},
    "L2": {"input": 0.000075, "output": 0.0003},
    "L3": {"input": 0.00125, "output": 0.005},
    "L4": {"input": 0.00125, "output": 0.005},
}

DAILY_COST_LIMIT_USD: float = float(os.getenv("AI_DAILY_COST_LIMIT_USD", "5.0"))
CACHE_TTL_SECONDS: int = int(os.getenv("AI_ROUTER_CACHE_TTL_SECONDS", "3600"))

_response_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_gemini_client = None


def _cache_get(prompt_hash: str) -> Optional[Dict[str, Any]]:
    if prompt_hash in _response_cache:
        ts, data = _response_cache[prompt_hash]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return data
        del _response_cache[prompt_hash]
    return None


def _cache_put(prompt_hash: str, result: Dict[str, Any]) -> None:
    now = time.time()
    for k in list(_response_cache.keys()):
        if now - _response_cache[k][0] > CACHE_TTL_SECONDS:
            del _response_cache[k]
    _response_cache[prompt_hash] = (now, result)


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else ""
        if not api_key:
            return None
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


async def _get_today_cost() -> float:
    try:
        from src.database import Database
        db = Database()
        today = time.strftime("%Y-%m-%d")
        row = await db.fetch_one(
            "SELECT SUM(cost_usd) as total FROM ai_usage WHERE date(timestamp) = ?",
            (today,),
        )
        return float(row["total"] or 0.0) if row else 0.0
    except Exception:
        return 0.0


async def _maybe_degrade_tier(tier: str) -> str:
    cost = await _get_today_cost()
    if cost >= DAILY_COST_LIMIT_USD:
        logger.warning(
            "AI daily cost threshold exceeded; degrading tier",
            cost=cost,
            limit=DAILY_COST_LIMIT_USD,
            from_tier=tier,
            to_tier="L1",
        )
        return "L1"
    return tier


def _estimate_cost(tier: str, tokens_in: int, tokens_out: int) -> float:
    rates = TIER_COST_PER_1K.get(tier, {"input": 0.0001, "output": 0.0005})
    return (tokens_in / 1000.0) * rates["input"] + (tokens_out / 1000.0) * rates["output"]


async def _log_usage(
    task_type: str,
    tier: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    success: bool,
    user_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    try:
        from src.database import Database
        db = Database()
        await db.execute_write(
            """
            INSERT INTO ai_usage (
                task_type, tier, model, tokens_in, tokens_out,
                cost_usd, latency_ms, success, user_id, lead_id, error, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                task_type,
                tier,
                model,
                tokens_in,
                tokens_out,
                cost_usd,
                latency_ms,
                1 if success else 0,
                user_id,
                lead_id,
                error,
            ),
        )
    except Exception as e:
        logger.debug("Failed to log AI usage to DB", error=str(e))


def _error_result(error_msg: str, task_type: str, tier: str, latency_ms: int) -> Dict[str, Any]:
    return {
        "text": "",
        "model": "none",
        "tier": tier,
        "task_type": task_type,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "success": False,
        "cached": False,
        "error": error_msg,
    }


async def get_daily_summary(date: Optional[str] = None) -> Dict[str, Any]:
    try:
        from src.database import Database
        db = Database()
        target_date = date or time.strftime("%Y-%m-%d")
        rows = await db.fetch_all(
            """
            SELECT
                task_type,
                tier,
                COUNT(*) as calls,
                SUM(tokens_in) as total_in,
                SUM(tokens_out) as total_out,
                SUM(cost_usd) as total_cost,
                AVG(latency_ms) as avg_latency
            FROM ai_usage
            WHERE date(timestamp) = ?
            GROUP BY task_type, tier
            """,
            (target_date,),
        )
        return {
            "date": target_date,
            "summary": rows or [],
            "daily_limit_usd": DAILY_COST_LIMIT_USD,
        }
    except Exception as e:
        return {"error": str(e), "date": date}
