"""Background scheduler for periodic AmoCRM call recordings & voice notes analysis.

Periodically scans active leads in AmoCRM to discover unprocessed voice notes
and audio call recordings, runs the Call Intelligence pipeline, generates conversion
advice, and schedules tasks.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.settings import settings

logger = logging.getLogger("CallAnalysisScheduler")


class CallScanResult:
    """Statistics summary for a single scan iteration."""

    def __init__(self) -> None:
        self.scanned_leads: int = 0
        self.processed_calls: int = 0
        self.errors: int = 0
        self.start_time: datetime = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None

    def finish(self) -> "CallScanResult":
        self.end_time = datetime.now(timezone.utc)
        return self

    def duration_seconds(self) -> float:
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanned_leads": self.scanned_leads,
            "processed_calls": self.processed_calls,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds(), 2),
        }


def _is_eligible_for_scan(lead: Dict[str, Any]) -> bool:
    """Determine if a lead should be inspected for call recordings."""
    if not isinstance(lead, dict):
        return False
    lead_id = lead.get("id")
    if not lead_id:
        return False
    status_id = lead.get("status_id")
    # Exclude closed-lost or won if needed, or scan recent active pipelines
    closed_loss = getattr(settings, "AMOCRM_LOST_STATUS_ID", 143)
    if status_id == closed_loss:
        return False
    return True


async def _fetch_scan_candidates(amocrm: Any, limit: int = 25) -> List[Dict[str, Any]]:
    """Retrieve recent active leads from AmoCRM."""
    candidates: List[Dict[str, Any]] = []
    try:
        getter = getattr(amocrm, "get_leads", None) or getattr(amocrm, "get_all_leads", None)
        if callable(getter):
            res = getter(limit=limit)
            leads = await res if asyncio.iscoroutine(res) else res
            if isinstance(leads, list):
                candidates = [l for l in leads if _is_eligible_for_scan(l)]
    except Exception as exc:
        logger.warning("[CALL-SCHEDULER] Failed to fetch scan candidates: %s", exc)
    return candidates


async def run_call_analysis_scan(
    amocrm: Optional[Any] = None,
    db: Optional[Any] = None,
    limit: int = 20,
) -> CallScanResult:
    """Execute a single sweep of candidate leads to transcribe & analyze calls."""
    result = CallScanResult()

    if not getattr(settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True):
        logger.debug("[CALL-SCHEDULER] ENABLE_AMOCRM_CALL_ANALYSIS is disabled.")
        return result.finish()

    try:
        from src.services.api_server.helpers import _get_amocrm_instance, _get_db_instance
        from src.services.core.call_analyzer import CallAnalyzer

        client = amocrm or _get_amocrm_instance()
        database = db or await _get_db_instance()
        analyzer = CallAnalyzer(amocrm=client, db=database)

        candidates = await _fetch_scan_candidates(client, limit=limit)
        result.scanned_leads = len(candidates)

        min_dur = getattr(settings, "AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS", 10)

        for lead in candidates:
            lead_id = lead.get("id")
            if not lead_id:
                continue
            try:
                phone = ""
                if hasattr(client, "get_lead_phone"):
                    p_res = client.get_lead_phone(lead_id)
                    phone = (await p_res if asyncio.iscoroutine(p_res) else p_res) or ""

                processed = await analyzer.process_call_recordings_for_lead(
                    lead_id=int(lead_id),
                    caller_phone=str(phone),
                    responsible_user_id=lead.get("responsible_user_id"),
                    min_call_duration_seconds=min_dur,
                )
                if processed:
                    result.processed_calls += len(processed)
            except Exception as proc_exc:
                result.errors += 1
                logger.error(
                    "[CALL-SCHEDULER] Error processing lead %s: %s",
                    lead_id,
                    proc_exc,
                    exc_info=True,
                )

        # 2. Process contact-level call recordings automatically
        try:
            if hasattr(analyzer, "analyze_recent_contact_calls"):
                c_stats = await analyzer.analyze_recent_contact_calls(
                    limit=20,
                    min_call_duration_seconds=min_dur,
                )
                result.processed_calls += int(c_stats.get("contact_calls_processed") or 0)
        except Exception as c_exc:
            logger.debug("[CALL-SCHEDULER] Contact calls sweep skipped: %s", c_exc)

        # 3. Continuous automatic historical backfill (catches any downtime recordings)
        try:
            if hasattr(analyzer, "backfill_call_recordings"):
                b_stats = await analyzer.backfill_call_recordings(
                    limit=15,
                    max_pages_per_run=3,
                    min_call_duration_seconds=min_dur,
                )
                result.processed_calls += int(b_stats.get("calls_processed") or 0)
        except Exception as b_exc:
            logger.debug("[CALL-SCHEDULER] Automatic backfill sweep skipped: %s", b_exc)

        logger.info(
            "[CALL-SCHEDULER] Sweep complete: %d leads scanned, %d calls processed, %d errors in %.2fs",
            result.scanned_leads,
            result.processed_calls,
            result.errors,
            result.duration_seconds(),
        )

    except Exception as sweep_exc:
        result.errors += 1
        logger.error("[CALL-SCHEDULER] Sweep failed with exception: %s", sweep_exc, exc_info=True)

    return result.finish()


async def call_analysis_loop(interval_seconds: int = 180) -> None:
    """Continuous background loop for scanning and analyzing AmoCRM calls."""
    logger.info(
        "[CALL-SCHEDULER] Starting background Call Intelligence loop (interval=%ds)...",
        interval_seconds,
    )
    # Initial sleep to allow main services to boot cleanly
    await asyncio.sleep(15)

    while True:
        try:
            if getattr(settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True):
                await run_call_analysis_scan(limit=25)
            else:
                logger.debug("[CALL-SCHEDULER] Skipping loop iteration (disabled).")
        except asyncio.CancelledError:
            logger.info("[CALL-SCHEDULER] Background loop received cancellation.")
            break
        except Exception as loop_exc:
            logger.error("[CALL-SCHEDULER] Unexpected loop error: %s", loop_exc, exc_info=True)

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("[CALL-SCHEDULER] Background loop cancelled during sleep.")
            break
