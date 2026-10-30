"""Call analysis integration; private script learning has no outbound messages."""
import logging

from src.services.call_analytics.winning_script_evolver import WinningScriptEvolver

logger = logging.getLogger(__name__)


async def capture_script_sample(note, lead_id, call_id, transcript, analysis):
    try:
        if analysis.get("category") != "Mijoz" or not analysis.get("rubrik_amal_qiladi"):
            return
        # Unknown recording time must not be substituted with analysis time.
        occurred_at = int(note.get("created_at") or 0)
        await WinningScriptEvolver().evolve_from_call(
            lead_id=lead_id, caller_phone="", manager_name="", duration_seconds=0,
            transcript=transcript, analysis=analysis, call_id=call_id, occurred_at=occurred_at,
        )
    except Exception as exc:
        logger.warning("[SCRIPT LEARNING] Capture failed: %s", type(exc).__name__)


async def refresh_scripts(amocrm):
    try:
        return await WinningScriptEvolver().reconcile(amocrm, min_interval=3600)
    except Exception as exc:
        logger.warning("[SCRIPT LEARNING] Refresh failed: %s", type(exc).__name__)
        return {"errors": 1, "updated_scripts": 0}
