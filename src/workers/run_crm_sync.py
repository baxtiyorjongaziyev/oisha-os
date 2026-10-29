#!/usr/bin/env python3
"""CRM Sync Worker — Entry Point for systemd."""

import asyncio
import logging
import sys
from pathlib import Path

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

from src.workers.call_intel_worker import run_crm_sync_worker

if __name__ == "__main__":
    asyncio.run(run_crm_sync_worker())