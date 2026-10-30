"""Bounded contextual-quality replay over existing transcripts; no CRM/payroll writes."""
import asyncio
import time

from src.services.call_analytics.quality_hook import contextual_review
from src.services.sales_quality.reviews import QualityReviews
from src.services.utils.db_rows import fetch_rows


async def backfill_quality(db, analyzer, limit=3, store=None):
    store = store or await asyncio.to_thread(QualityReviews)
    rows = await fetch_rows(db,
        "SELECT call_id, lead_id, manager_id, transcript FROM call_analyses "
        "WHERE call_id IS NOT NULL AND transcript IS NOT NULL AND LENGTH(transcript) >= 40 "
        "ORDER BY id DESC LIMIT 200")
    result = {"examined": len(rows), "processed": 0, "review_ready": 0, "unknown": 0}
    seen = set()
    for row in rows:
        call_id = str(row["call_id"])
        if call_id in seen:
            continue
        seen.add(call_id)
        current = await asyncio.to_thread(store.get, call_id)
        if current and (current.get("review_ready") or current.get("reviews")
                        or current["updated_at"] > time.time() - 3600):
            continue
        evaluation = await contextual_review(analyzer, row["transcript"])
        await asyncio.to_thread(store.save, call_id, row["lead_id"], row["manager_id"],
                                {**evaluation, "direction": "unknown", "origin": "stored_transcript_replay"})
        result["processed"] += 1
        result["review_ready"] += int(evaluation["review_ready"])
        result["unknown"] += int(evaluation["score"] is None)
        if result["processed"] >= max(1, min(limit, 10)):
            break
    return result
