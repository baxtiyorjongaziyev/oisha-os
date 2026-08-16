"""Weekly self-report of Hisobchi AI's own uncertainty (hisobchi_ai_gaps).

Posts a short summary to the finance group automatically — no command
needed. Runs once a week; if there were zero gaps, still posts a short
"all clear" line so the owner knows the check ran rather than silently
never firing.
"""
import logging

logger = logging.getLogger(__name__)


async def run_hisobchi_gap_report(hisobchi_engine, bot_client, finance_group_id: int) -> None:
    if hisobchi_engine is None or bot_client is None or not finance_group_id:
        logger.debug("[HISOBCHI-GAPS] Missing engine/bot_client/finance_group_id, skipping.")
        return

    try:
        text = await hisobchi_engine.format_ai_gaps_report_uz(since_days=7)
        await bot_client.send_message(finance_group_id, text)
        logger.info("[HISOBCHI-GAPS] Weekly AI gap report sent.")
    except Exception:
        logger.error("[HISOBCHI-GAPS] Failed to send weekly AI gap report", exc_info=True)
