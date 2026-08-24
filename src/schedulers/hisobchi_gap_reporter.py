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


async def hisobchi_gap_report_loop(hisobchi_engine, bot_client) -> None:
    """Weekly (Monday 09:30) self-report of Hisobchi AI uncertainty log."""
    import asyncio
    from src.services.core.finance.handlers.utils import _get_finance_config
    from src.time_utils import get_local_now

    await asyncio.sleep(90)
    while True:
        try:
            now = get_local_now()
            if now.weekday() == 0 and now.hour == 9 and now.minute == 30:
                finance_group_id, _, _ = _get_finance_config()
                await run_hisobchi_gap_report(
                    hisobchi_engine=hisobchi_engine,
                    bot_client=bot_client,
                    finance_group_id=finance_group_id,
                )
                await asyncio.sleep(61)
        except Exception as e:
            logger.error("[HISOBCHI-GAPS] Error in weekly gap report loop: %s", e)
        await asyncio.sleep(30)
