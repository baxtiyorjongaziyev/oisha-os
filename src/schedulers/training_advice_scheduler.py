"""Kunlik AI trening tavsiyasi scheduleri.

Eng past `overall_score`li menejerni topib, uning eng zaif playbook
bosqichi bo'yicha (`_compute_weak_stages`) AI orqali qisqa tavsiya
generatsiya qiladi va `training_advice` jadvaliga yozadi. AI so'rov
faqat shu kunlik siklda yuboriladi — HTTP so'rov davomida hech qachon
chaqirilmaydi (`/api/sales-quality/training-advice` faqat DB'dan o'qiydi).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List

from src.database import get_db
from src.services.sales_quality.helpers import _fetch_call_analysis_rows, _row_to_dict
from src.services.sales_quality.weak_stages import _compute_weak_stages
from src.services.utils.free_ai_router import FreeAIProviderRouter

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """
Sen Jon Branding agentligi uchun sotuv menejerlarini o'qitish bo'yicha AI murabbiysan.

Menejer: {manager_name}
Eng zaif bosqich: {weak_stage_label} (o'rtacha ball: {weak_stage_rate}%)

Shu menejerga 2-3 gapdan iborat, aniq va amaliy tavsiya yoz — nima ustida
ishlashi kerakligini va qanday qilib yaxshilashi mumkinligini tushuntir.
Javobni FAQAT o'zbek tilida yoz, inglizcha so'zlardan foydalanma.
"""


def _pick_lowest_scoring_manager(rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Har bir manager_id bo'yicha o'rtacha ball hisoblab, eng pastini qaytaradi."""
    by_manager: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        manager_id = row.get("manager_id")
        if manager_id is None:
            continue
        by_manager[manager_id].append(row)

    if not by_manager:
        return None

    best_manager_id = None
    best_avg = None
    best_rows: List[Dict[str, Any]] = []
    for manager_id, manager_rows in by_manager.items():
        scores = [
            r.get("overall_score") for r in manager_rows
            if isinstance(r.get("overall_score"), (int, float))
            and not isinstance(r.get("overall_score"), bool)
        ]
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        if best_avg is None or avg < best_avg:
            best_avg = avg
            best_manager_id = manager_id
            best_rows = manager_rows

    manager_name = next(
        (r.get("manager_name") for r in best_rows if r.get("manager_name")),
        f"Manager-{best_manager_id}",
    )
    return {"manager_id": best_manager_id, "manager_name": manager_name, "rows": best_rows}


async def run_training_advice_cycle() -> None:
    """Bitta sikl: eng past ballli menejerni topib, tavsiya yozadi."""
    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.warning("[TRAINING-ADVICE] Failed to fetch call_analyses: %s", exc)
        return

    if not rows:
        logger.info("[TRAINING-ADVICE] No call_analyses rows yet — skipping cycle.")
        return

    rows = [
        _row_to_dict(r, ["manager_id", "manager_name", "overall_score", "scores", "weaknesses"])
        for r in rows
    ]

    target = _pick_lowest_scoring_manager(rows)
    if target is None:
        logger.info("[TRAINING-ADVICE] No manager_id found in rows — skipping cycle.")
        return

    weak_stage_records = [
        {"scores": r.get("scores"), "weaknesses": r.get("weaknesses")}
        for r in target["rows"]
    ]
    weak_stages = _compute_weak_stages(weak_stage_records, limit=1)
    if not weak_stages:
        logger.info(
            "[TRAINING-ADVICE] No stage data for manager %s — skipping cycle.",
            target["manager_id"],
        )
        return

    weakest = weak_stages[0]
    prompt = _PROMPT_TEMPLATE.format(
        manager_name=target["manager_name"],
        weak_stage_label=weakest["label"],
        weak_stage_rate=weakest["rate"],
    )

    try:
        router = FreeAIProviderRouter()
        result = await router.generate_text(prompt=prompt, max_tokens=400, temperature=0.4)
        advice_text = (result.text or "").strip()
    except Exception as exc:
        logger.warning("[TRAINING-ADVICE] AI generation failed: %s", exc)
        return

    if not advice_text:
        logger.info("[TRAINING-ADVICE] AI returned empty advice — skipping write.")
        return

    db = get_db()
    await db.intelligence.upsert_training_advice(
        manager_id=target["manager_id"],
        manager_name=target["manager_name"],
        advice_text=advice_text,
    )
    logger.info("[TRAINING-ADVICE] Wrote advice for manager_id=%s", target["manager_id"])


async def training_advice_loop() -> None:
    """Har 24 soatda bir marta ishlaydigan orqa fon sikli."""
    await asyncio.sleep(120)  # Boot delay
    logger.info("[TRAINING-ADVICE] Daily loop started.")
    while True:
        try:
            await run_training_advice_cycle()
        except Exception as exc:
            logger.error("[TRAINING-ADVICE] Error in loop: %s", exc)
        await asyncio.sleep(86400)
