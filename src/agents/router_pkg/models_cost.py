"""
AI Router models catalog, cost tracking, caching, and usage logging.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Dict, Literal, Optional

import structlog

from src.settings import settings

logger = structlog.get_logger()

TaskType = Literal["draft", "classify", "summarize", "reason", "negotiate", "escalate"]

TASK_TO_TIER: Dict[str, str] = {
    "draft": "L1",
    "classify": "L1",
    "summarize": "L1",
    "reason": "L3",
    "negotiate": "L3",
    "escalate": "L4",
}

_SHARED_GEMINI_MODEL = settings.GEMINI_CALL_MODEL
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "L1": {
        "model": os.environ.get("AI_ROUTER_L1_MODEL", _SHARED_GEMINI_MODEL),
        "cost_in_per_1m": 0.0,
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 2048,
    },
    "L2": {
        "model": os.environ.get("AI_ROUTER_L2_MODEL", _SHARED_GEMINI_MODEL),
        "cost_in_per_1m": 0.0,
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 1024,
    },
    "L3": {
        "model": os.environ.get("AI_ROUTER_L3_MODEL", settings.FREE_AI_GEMINI_MODEL),
        "cost_in_per_1m": 0.0,
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 4096,
    },
    "L4": {
        "model": os.environ.get("AI_ROUTER_L4_MODEL", settings.FREE_AI_GEMINI_MODEL),
        "cost_in_per_1m": 0.0,
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 8192,
    },
}

DAILY_COST_SOFT_LIMIT = float(os.environ.get("AI_DAILY_COST_SOFT_LIMIT", "3.0"))
DAILY_COST_HARD_LIMIT = float(os.environ.get("AI_DAILY_COST_HARD_LIMIT", "10.0"))
CACHE_TTL_SEC = int(os.environ.get("AI_ROUTER_CACHE_TTL", "3600"))

_SIMPLE_TASK_PROVIDERS: tuple[str, ...] = ("groq", "cloudflare", "ollama")
_COMPLEX_FALLBACK_PROVIDERS: tuple[str, ...] = ("cloudflare", "ollama")

_cache: Dict[str, Dict[str, Any]] = {}


def _cache_get(prompt_hash: str) -> Optional[Dict[str, Any]]:
    entry = _cache.get(prompt_hash)
    if not entry:
        return None
    if time.time() - entry["ts"] > CACHE_TTL_SEC:
        _cache.pop(prompt_hash, None)
        return None
    return entry["result"]


def _cache_put(prompt_hash: str, result: Dict[str, Any]) -> None:
    if result.get("success"):
        _cache[prompt_hash] = {"ts": time.time(), "result": result}
        if len(_cache) > 1000:
            oldest = min(_cache.items(), key=lambda kv: kv[1]["ts"])
            _cache.pop(oldest[0], None)


async def _get_today_cost() -> float:
    try:
        from src.database import Database

        db = Database()
        async with db.get_conn() as conn:
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM ai_usage "
                "WHERE DATE(created_at) = DATE('now')"
            )
            row = await cursor.fetchone()
            return float(row[0] if row else 0.0)
    except Exception as e:
        logger.debug("[AI_ROUTER] Could not fetch today cost: %s", e)
        return 0.0


async def _maybe_degrade_tier(tier: str) -> str:
    if tier == "L1":
        return tier
    today = await _get_today_cost()
    if today >= DAILY_COST_HARD_LIMIT:
        logger.warning("[AI_ROUTER] Hard limit hit ($%.2f). Degrading %s -> L1", today, tier)
        return "L1"
    if today >= DAILY_COST_SOFT_LIMIT and tier in ("L3", "L4"):
        logger.warning("[AI_ROUTER] Soft limit hit ($%.2f). Degrading %s -> L1", today, tier)
        return "L1"
    return tier


def _estimate_cost(tier: str, tokens_in: int, tokens_out: int) -> float:
    cfg = MODEL_CATALOG[tier]
    return (
        tokens_in * cfg["cost_in_per_1m"] / 1_000_000
        + tokens_out * cfg["cost_out_per_1m"] / 1_000_000
    )


async def _log_usage(
    *,
    task_type: str,
    tier: str,
    model: str,
    prompt_hash: str,
    prompt_preview: str,
    response_preview: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    user_id: Optional[int],
    context: Optional[Dict[str, Any]],
    success: bool,
    error: Optional[str],
) -> None:
    try:
        from src.database import Database

        db = Database()
        async with db.get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO ai_usage
                  (created_at, task_type, tier, model, prompt_hash, prompt_preview,
                   response_preview, tokens_in, tokens_out, cost_usd, latency_ms,
                   user_id, context_json, success, error)
                VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_type,
                    tier,
                    model,
                    prompt_hash,
                    prompt_preview,
                    response_preview,
                    tokens_in,
                    tokens_out,
                    cost_usd,
                    latency_ms,
                    user_id,
                    json.dumps(context or {}, ensure_ascii=False),
                    1 if success else 0,
                    error,
                ),
            )
            await conn.commit()
    except Exception as e:
        logger.debug("[AI_ROUTER] ai_usage log failed (non-fatal): %s", e)


def _error_result(
    error: str,
    *,
    task_type: str,
    tier: str,
    model: str,
    prompt_hash: str,
    start: float,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    latency_ms = int((time.time() - start) * 1000)
    result = {
        "text": "",
        "model": model,
        "tier": tier,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "success": False,
        "error": error,
        "cached": False,
        "prompt_hash": prompt_hash,
    }
    try:
        asyncio.create_task(
            _log_usage(
                task_type=task_type,
                tier=tier,
                model=model,
                prompt_hash=prompt_hash,
                prompt_preview="",
                response_preview="",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                user_id=user_id,
                context=context,
                success=False,
                error=error,
            )
        )
    except RuntimeError:
        pass
    return result


async def get_daily_summary(date: Optional[str] = None) -> Dict[str, Any]:
    try:
        from src.database import Database

        db = Database()
        async with db.get_conn() as conn:
            if not date:
                where_clause = "DATE(created_at) = DATE('now')"
                params: tuple = ()
            else:
                where_clause = "DATE(created_at) = ?"
                params = (date,)
            cursor = await conn.execute(
                f"""
                SELECT
                  COUNT(*) AS calls,
                  SUM(tokens_in) AS tok_in,
                  SUM(tokens_out) AS tok_out,
                  SUM(cost_usd) AS cost,
                  AVG(latency_ms) AS lat,
                  SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok,
                  SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS fail
                FROM ai_usage WHERE {where_clause}
            """,  # nosec
                params,
            )
            row = await cursor.fetchone()
            cursor2 = await conn.execute(
                f"""
                SELECT model, COUNT(*) AS c, SUM(cost_usd) AS cost_sum
                FROM ai_usage WHERE {where_clause}
                GROUP BY model ORDER BY c DESC
            """,  # nosec
                params,
            )
            by_model = [
                {"model": r[0], "calls": r[1], "cost_usd": r[2]} async for r in cursor2
            ]
            return {
                "date": date or "today",
                "calls": row[0] or 0,
                "tokens_in": row[1] or 0,
                "tokens_out": row[2] or 0,
                "cost_usd": round(row[3] or 0.0, 4),
                "avg_latency_ms": round(row[4] or 0.0, 1),
                "ok": row[5] or 0,
                "fail": row[6] or 0,
                "by_model": by_model,
            }
    except Exception as e:
        logger.error("[AI_ROUTER] daily summary failed: %s", e)
        return {"error": str(e)}
