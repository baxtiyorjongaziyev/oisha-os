"""Dedicated 24/7 Meta Leads Ingestion & Multi-Channel Pipeline Worker.

Runs as an isolated, lightweight systemd service independent of Telethon userbots
or AI chat agents, guaranteeing zero interruption for advertising leads.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import signal
import sys
from pathlib import Path

# Ensure root workspace is in sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("LeadgenWorker")

HEARTBEAT_PATH = _ROOT / "data" / "leadgen_heartbeat.json"


async def heartbeat_loop() -> None:
    """Write heartbeat status every 30 seconds for external monitors."""
    from src.services.core.instagram.leadgen_watchdog import audit_leadgen_health

    while True:
        try:
            stats = audit_leadgen_health()
            payload = {
                "timestamp": datetime.datetime.now().isoformat(),
                "pid": os.getpid(),
                "status": "healthy",
                "stats": stats,
            }
            HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("[LEADGEN HEARTBEAT] Error recording heartbeat: %s", exc)

        await asyncio.sleep(30)


async def main() -> None:
    """Launch dedicated 24/7 Meta leads pipelines."""
    logger.info("=" * 60)
    logger.info("🚀 Starting Oisha-OS Dedicated 24/7 Meta Leads Worker (PID: %d)", os.getpid())
    logger.info("=" * 60)

    from src.schedulers.meta_leadgen_scheduler import meta_leadgen_loop
    from src.schedulers.leadgen_status_reporter import leadgen_watchdog_and_reporter_loop

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown_signal(sig_name: str) -> None:
        logger.info("Received %s signal, gracefully stopping worker...", sig_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown_signal, sig.name)
        except NotImplementedError:
            # Signal handling on Windows (fallback)
            pass

    tasks = [
        asyncio.create_task(meta_leadgen_loop(), name="meta_leadgen_loop"),
        asyncio.create_task(leadgen_watchdog_and_reporter_loop(), name="watchdog_loop"),
        asyncio.create_task(heartbeat_loop(), name="heartbeat_loop"),
    ]

    await stop_event.wait()
    logger.info("Cancelling background leadgen tasks...")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Leadgen worker successfully stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Leadgen worker exited.")
