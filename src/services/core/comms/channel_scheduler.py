"""Channel Scout Scheduler — Daily scanning of business trainer channels."""
from __future__ import annotations

import logging
from datetime import datetime, time

logger = logging.getLogger(__name__)


async def daily_channel_scout(client=None, amocrm=None, db=None, agent_context=None) -> dict:
    """
    Daily task: Scan business trainer channels for leads.
    Scheduled: 10:00, 14:00, 18:00 (Tashkent time)
    """
    if not client:
        logger.warning("[CHANNEL-SCOUT-SCHEDULER] No Telethon client provided")
        return {"status": "skipped", "reason": "no_client"}

    from src.services.core.channel_scout import ChannelScout
    from src.services.core.channel_lead_extractor import ChannelLeadExtractor

    try:
        scout = ChannelScout(client=client)
        extractor = ChannelLeadExtractor(amocrm_adapter=amocrm, db=db)

        logger.info("[CHANNEL-SCOUT-SCHEDULER] Starting daily channel scan...")

        # Phase 1: Analyze all channels
        scan_results = await scout.scan_all_channels()
        top_channels = scout.get_top_channels(limit=5)

        logger.info(f"[CHANNEL-SCOUT-SCHEDULER] Scanned {len(scan_results)} channels")
        logger.info(f"[CHANNEL-SCOUT-SCHEDULER] Top channels: {[ch['name'] for ch in top_channels]}")

        # Phase 2: Extract leads from top channels
        total_leads = 0
        for channel_info in top_channels:
            channel_name = channel_info["name"]
            logger.info(f"[CHANNEL-SCOUT-SCHEDULER] Extracting leads from @{channel_name}...")

            leads = await scout.extract_leads_from_channel(channel_name, limit=20)
            if leads:
                processed = await extractor.batch_process_leads(leads)
                total_leads += len(processed)
                logger.info(f"[CHANNEL-SCOUT-SCHEDULER] {len(processed)} leads extracted from @{channel_name}")

        # Phase 3: Report
        scout_report = scout.report()
        extractor_report = extractor.report()

        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "channels_scanned": len(scan_results),
            "top_channels": top_channels,
            "total_leads_extracted": total_leads,
            "scout_report": scout_report,
            "extractor_report": extractor_report,
        }

        # Optional: Send daily digest to admin
        if agent_context and hasattr(agent_context, "send_admin_notification"):
            await agent_context.send_admin_notification(
                f"✅ Channel Scout completed\n"
                f"Channels: {len(scan_results)}\n"
                f"Leads: {total_leads}\n"
                f"Top channel: @{top_channels[0]['name'] if top_channels else '?'}"
            )

        return result

    except Exception as exc:
        logger.error(f"[CHANNEL-SCOUT-SCHEDULER] Daily scan failed: {exc}")
        return {
            "status": "failed",
            "error": str(exc),
            "timestamp": datetime.now().isoformat(),
        }


async def setup_channel_scout_scheduler(scheduler=None, client=None, amocrm=None, db=None):
    """Register daily channel scout tasks with scheduler."""
    if not scheduler:
        logger.warning("[CHANNEL-SCOUT] No scheduler provided, skipping setup")
        return

    # Schedule 3x daily: 10:00, 14:00, 18:00 (Tashkent time)
    scan_times = [time(10, 0), time(14, 0), time(18, 0)]

    for scan_time in scan_times:
        scheduler.add_job(
            daily_channel_scout,
            "cron",
            hour=scan_time.hour,
            minute=scan_time.minute,
            args=[],
            kwargs={"client": client, "amocrm": amocrm, "db": db},
            id=f"channel_scout_{scan_time.hour}_{scan_time.minute}",
            name=f"Channel Scout @ {scan_time.strftime('%H:%M')}",
            replace_existing=True,
        )

    logger.info(
        f"[CHANNEL-SCOUT] Scheduled 3 daily scans at {', '.join([t.strftime('%H:%M') for t in scan_times])}"
    )
