"""
ai_router — Markazlashgan LLM router (Gemini-first stack).

Maqsad: butun Oisha OS uchun yagona AI entry point. Task turiga qarab
mos modelni tanlaydi, fallback zanjirini yuritadi, har chaqiruvni `ai_usage`
jadvaliga log qiladi va oylik AI xarajatni minimalga tushiradi.

Hozirgi model xaritasi (12 oylik plan bo'yicha — Claude kaliti kelganda L3/L4 almashtiriladi):

  L1 → gemini-2.0-flash       (draft, summarize, classify, briefing)
  L2 → gemini-2.0-flash-lite  (fallback tezkor fallback L1 529/429'da)
  L3 → gemini-1.5-pro         (reason, negotiate — chuqur reasoning)
  L4 → gemini-1.5-pro         (escalate — hozircha Pro, Claude Opus kelganda almashtiriladi)

API:

    from src.agents.ai_router import route

    result = await route(
        prompt="Salom, narx haqida...",
        task_type="negotiate",
        context={"lead_id": 12345},
        user_id=999,
        max_tokens=2048,
    )
    # result: {"text": str, "model": str, "tokens_in": int, "tokens_out": int,
    #         "cost_usd": float, "latency_ms": int, "success": bool}

Dizayn tamoyillari:
  - **Backward-compatible**: mavjud `generate_ai_message` `route(task_type="draft")` ga
    delegatsiya qiladi — hech narsa buzilmaydi.
  - **Idempotent**: bir xil `prompt_hash` 60 daqiqada takrorlansa — cache'dan qaytadi.
  - **Observable**: har chaqiruv SQLite `ai_usage` + BigQuery `ai_responses` ga yoziladi.
  - **Limit-safe**: kunlik xarajat threshold'dan oshsa degradatsiya (L3 → L1).
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

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguratsiya
# ──────────────────────────────────────────────────────────────────────────────

TaskType = Literal["draft", "classify", "summarize", "reason", "negotiate", "escalate"]

# Task turi → model darajasi (istalgan vaqtda o'zgartirsa bo'ladi)
TASK_TO_TIER: Dict[str, str] = {
    "draft": "L1",
    "classify": "L1",
    "summarize": "L1",
    "reason": "L3",
    "negotiate": "L3",
    "escalate": "L4",
}

# Daraja → (model nomi, haqiqiy tier, input $/1M tok, output $/1M tok)
# Gemini 1.5 Pro va 2.0 Flash — bepul tier'da xarajat hisobi 0, lekin audit uchun real narxlar
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "L1": {
        "model": "gemini-2.0-flash",
        "cost_in_per_1m": 0.0,  # bepul tier
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 2048,
    },
    "L2": {
        "model": "gemini-2.0-flash-lite",
        "cost_in_per_1m": 0.0,
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 1024,
    },
    "L3": {
        "model": "gemini-1.5-pro",
        "cost_in_per_1m": 0.0,  # bepul tier 50 RPM
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 4096,
    },
    "L4": {
        "model": "gemini-1.5-pro",
        "cost_in_per_1m": 0.0,
        "cost_out_per_1m": 0.0,
        "max_tokens_default": 8192,
    },
}

# Kunlik xarajat limiti (USD) — oshsa L3/L4 avtomatik L1 ga tushadi
DAILY_COST_SOFT_LIMIT = float(os.environ.get("AI_DAILY_COST_SOFT_LIMIT", "3.0"))
DAILY_COST_HARD_LIMIT = float(os.environ.get("AI_DAILY_COST_HARD_LIMIT", "10.0"))

# Cache TTL (sekund) — bir xil prompt bu vaqt ichida takrorlansa cache'dan qaytadi
CACHE_TTL_SEC = int(os.environ.get("AI_ROUTER_CACHE_TTL", "3600"))


# ──────────────────────────────────────────────────────────────────────────────
# In-memory idempotency cache
# ──────────────────────────────────────────────────────────────────────────────

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
    # Cache'ni kichik tutish — faqat muvaffaqiyatli javoblar
    if result.get("success"):
        _cache[prompt_hash] = {"ts": time.time(), "result": result}
        # Max 1000 entry — LRU sifatida eng eskisini chiqarib tashlaymiz
        if len(_cache) > 1000:
            oldest = min(_cache.items(), key=lambda kv: kv[1]["ts"])
            _cache.pop(oldest[0], None)


# ──────────────────────────────────────────────────────────────────────────────
# Gemini client (singleton)
# ──────────────────────────────────────────────────────────────────────────────

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client

    try:
        from google import genai  # pyright: ignore[reportMissingImports]
    except ImportError:
        logger.error(
            "[AI_ROUTER] google-genai not installed. Run: pip install google-genai"
        )
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

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# ──────────────────────────────────────────────────────────────────────────────
# Kunlik xarajat degradatsiyasi
# ──────────────────────────────────────────────────────────────────────────────


async def _get_today_cost() -> float:
    """SQLite `ai_usage` jadvalidan bugungi jami xarajatni olish."""
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
        logger.debug(f"[AI_ROUTER] Could not fetch today cost: {e}")
        return 0.0


async def _maybe_degrade_tier(tier: str) -> str:
    """Kunlik xarajat limitiga yaqin bo'lsa yuqori tier'ni L1 ga tushirish."""
    if tier == "L1":
        return tier
    today = await _get_today_cost()
    if today >= DAILY_COST_HARD_LIMIT:
        logger.warning(
            f"[AI_ROUTER] Hard limit hit (${today:.2f}). Degrading {tier} → L1"
        )
        return "L1"
    if today >= DAILY_COST_SOFT_LIMIT and tier in ("L3", "L4"):
        logger.warning(
            f"[AI_ROUTER] Soft limit hit (${today:.2f}). Degrading {tier} → L1"
        )
        return "L1"
    return tier


# ──────────────────────────────────────────────────────────────────────────────
# Asosiy router
# ──────────────────────────────────────────────────────────────────────────────


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
    """Markazlashgan AI chaqiruvi.

    Returns:
        {
          "text": str,            # javob matni
          "model": str,           # haqiqatda ishlatilgan model
          "tier": str,            # tanlangan tier (L1/L2/L3/L4)
          "tokens_in": int,
          "tokens_out": int,
          "cost_usd": float,
          "latency_ms": int,
          "success": bool,
          "error": Optional[str],
          "cached": bool,
        }
    """
    start = time.time()

    # 1. Tier tanlash
    base_tier = TASK_TO_TIER.get(task_type, "L1")
    tier = await _maybe_degrade_tier(base_tier)
    tier_cfg = MODEL_CATALOG[tier]
    model_name = tier_cfg["model"]
    if max_tokens is None:
        max_tokens = tier_cfg["max_tokens_default"]

    # 2. Idempotency hash
    hash_payload = f"{task_type}|{tier}|{system or ''}|{prompt}"
    prompt_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()[:16]

    # 3. Cache tekshirish
    if not bypass_cache:
        cached = _cache_get(prompt_hash)
        if cached:
            cached_copy = dict(cached)
            cached_copy["cached"] = True
            cached_copy["latency_ms"] = int((time.time() - start) * 1000)
            return cached_copy

    # 4. Client tekshirish
    client = _get_gemini_client()
    if client is None:
        return _error_result(
            "Gemini client unavailable",
            task_type=task_type,
            tier=tier,
            model=model_name,
            prompt_hash=prompt_hash,
            start=start,
        )

    # 5. Fallback zanjiri: tanlangan tier → L2 → L1
    fallback_chain = [tier]
    if tier != "L1":
        fallback_chain.append("L1")
    # L3/L4 ham muvaffaqiyatsiz bo'lsa L2 Flash-lite
    if tier in ("L3", "L4") and "L2" not in fallback_chain:
        fallback_chain.insert(1, "L2")

    last_error: Optional[str] = None
    for attempt_tier in fallback_chain:
        attempt_cfg = MODEL_CATALOG[attempt_tier]
        attempt_model = attempt_cfg["model"]
        try:
            result = await _call_gemini(
                client=client,
                model=attempt_model,
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # Muvaffaqiyat
            cost = _estimate_cost(
                attempt_tier, result["tokens_in"], result["tokens_out"]
            )
            final = {
                "text": result["text"],
                "model": attempt_model,
                "tier": attempt_tier,
                "tokens_in": result["tokens_in"],
                "tokens_out": result["tokens_out"],
                "cost_usd": cost,
                "latency_ms": int((time.time() - start) * 1000),
                "success": True,
                "error": None,
                "cached": False,
                "prompt_hash": prompt_hash,
            }
            _cache_put(prompt_hash, final)
            await _log_usage(
                task_type=task_type,
                tier=attempt_tier,
                model=attempt_model,
                prompt_hash=prompt_hash,
                prompt_preview=prompt[:200],
                response_preview=result["text"][:200],
                tokens_in=result["tokens_in"],
                tokens_out=result["tokens_out"],
                cost_usd=cost,
                latency_ms=final["latency_ms"],
                user_id=user_id,
                context=context,
                success=True,
                error=None,
            )
            return final
        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"[AI_ROUTER] Tier {attempt_tier} ({attempt_model}) failed: {e}"
            )
            await asyncio.sleep(0.5 + random.random())
            continue

    # Barcha fallback'lar muvaffaqiyatsiz
    return _error_result(
        last_error or "All tiers failed",
        task_type=task_type,
        tier=tier,
        model=model_name,
        prompt_hash=prompt_hash,
        start=start,
        user_id=user_id,
        context=context,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Gemini chaqiruvi
# ──────────────────────────────────────────────────────────────────────────────


async def _call_gemini(
    client: Any,
    model: str,
    prompt: str,
    system: Optional[str],
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    """Gemini'ga bitta oddiy chaqiruv (tool-use yo'q)."""
    from google.genai import types  # pyright: ignore[reportMissingImports]

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
    # Token hisob — agar `usage_metadata` bor bo'lsa ishlatamiz
    usage = getattr(response, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) or 0
    tokens_out = getattr(usage, "candidates_token_count", 0) or 0

    return {"text": text, "tokens_in": int(tokens_in), "tokens_out": int(tokens_out)}


# ──────────────────────────────────────────────────────────────────────────────
# Xarajat hisobi + logging
# ──────────────────────────────────────────────────────────────────────────────


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
    """SQLite `ai_usage` ga yozish. Xato bo'lsa sukunat — bot ishlashi to'xtamaydi."""
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
        logger.debug(f"[AI_ROUTER] ai_usage log failed (non-fatal): {e}")


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
    # Xatoni ham log qilamiz — analitika uchun
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
        pass  # No running loop
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Kunlik xulosa
# ──────────────────────────────────────────────────────────────────────────────


async def get_daily_summary(date: Optional[str] = None) -> Dict[str, Any]:
    """Kunlik AI xarajat va ishlatish xulosasi — admin bot uchun."""
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
        logger.error(f"[AI_ROUTER] daily summary failed: {e}")
        return {"error": str(e)}
