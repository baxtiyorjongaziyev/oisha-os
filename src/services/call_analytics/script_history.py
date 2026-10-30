"""Bounded replay of already-transcribed calls discovered by the existing scanner."""
import asyncio
import logging
import time

from src.services.call_analytics.winning_script_evolver import WinningScriptEvolver
from src.services.utils.db_rows import fetch_rows

logger = logging.getLogger(__name__)


async def capture_historical_sample(analyzer, note, lead_id, call_id):
    """Reclassify up to three historical calls per analyzer/sweep, without CRM writes."""
    if not analyzer.db or getattr(analyzer, "_script_history_budget", 0) <= 0:
        return
    try:
        occurred_at = int(note.get("created_at") or 0)
        if occurred_at <= 0:
            return
        evolver = WinningScriptEvolver()
        now = int(time.time())
        if not await asyncio.to_thread(evolver.library.history_due, call_id, now):
            return
        rows = await fetch_rows(
            analyzer.db,
            "SELECT transcript, duration_seconds FROM call_analyses "
            "WHERE call_id = ? AND lead_id = ? AND source = 'amocrm' "
            "AND overall_score >= 75 ORDER BY id DESC LIMIT 1",
            [call_id, lead_id],
        )
        if not rows or not isinstance(rows[0].get("transcript"), str):
            return
        analyzer._script_history_budget -= 1
        await asyncio.to_thread(evolver.library.mark_history, call_id, now, False)
        analysis = await analyzer.analyze_transcript(
            transcript=rows[0]["transcript"], duration_seconds=rows[0]["duration_seconds"] or 0,
        )
        if not isinstance(analysis, dict):
            return
        await evolver.evolve_from_call(
            lead_id, "", "", rows[0]["duration_seconds"] or 0, rows[0]["transcript"], analysis,
            call_id=call_id, occurred_at=occurred_at,
        )
        # Unavailable model analysis is retried; a classified non-sales call is final.
        complete = analysis.get("rubrik_amal_qiladi") is True or analysis.get("category") in {"Oila", "Jamoa", "Shaxsiy"}
        await asyncio.to_thread(evolver.library.mark_history, call_id, now, complete)
    except Exception as exc:
        logger.warning("[SCRIPT LEARNING] Historical replay failed: %s", type(exc).__name__)
