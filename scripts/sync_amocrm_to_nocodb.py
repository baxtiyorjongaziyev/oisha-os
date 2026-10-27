"""
CLI runner to sync AmoCRM closed and archived leads to local PostgreSQL and NocoDB.
Usage:
    python scripts/sync_amocrm_to_nocodb.py [--max-pages 5]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.core.crm.amocrm_nocodb_syncer import AmoCRMNocoDBSyncer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sync_cli")


async def main():
    parser = argparse.ArgumentParser(description="Sync amoCRM leads to PostgreSQL/NocoDB")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pages per status (250 leads/page)")
    parser.add_argument("--init-only", action="store_true", help="Only initialize table schema")
    args = parser.parse_args()

    syncer = AmoCRMNocoDBSyncer()
    logger.info("Initializing PostgreSQL table...")
    syncer.init_tables()

    if args.init_only:
        logger.info("Initialization complete (--init-only).")
        return

    logger.info("Starting sync from amoCRM to PostgreSQL...")
    synced = await syncer.sync_closed_leads(max_pages=args.max_pages)
    logger.info("Successfully synced %s leads to PostgreSQL (amocrm_archived_leads).", synced)


if __name__ == "__main__":
    asyncio.run(main())
