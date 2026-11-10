#!/usr/bin/env python3
"""Run safe CRM/Drive sync from existing Oisha server cron.

Example:
  python scripts/safe_crm_drive_sync.py --lead-id 123
  python scripts/safe_crm_drive_sync.py --recent 100 --stage-existing

Defaults to folder links only; existing CRM file copies require opt-in.
Never deletes originals. For 24/7 automation schedule this on the server.
"""
import argparse
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.gdrive import GoogleDriveSync
from src.services.core.crm.safe_drive_automation import SafeCRMDriveAutomation
from src.settings import settings

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def report_telegram(message: str) -> bool:
    token = settings.BOT_TOKEN.get_secret_value()
    if not token or not settings.CRM_GROUP_ID:
        LOG.warning("CRM_GROUP_ID/BOT_TOKEN unavailable; Telegram report skipped")
        return False
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": settings.CRM_GROUP_ID, "text": message},
        timeout=20,
    )
    response.raise_for_status()
    return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--lead-id", type=int)
    source.add_argument("--recent", type=int, help="Number of recent leads, max 250")
    parser.add_argument("--stage-existing", action="store_true",
                        help="Copy and checksum CRM attachments; never delete")
    parser.add_argument("--telegram-report", action="store_true")
    args = parser.parse_args()
    if not settings.GDRIVE_OFFLOAD_FOLDER_ID:
        parser.error("GDRIVE_OFFLOAD_FOLDER_ID is required")
    amo = AmoCRMSync()
    drive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
    automation = SafeCRMDriveAutomation(amo, drive, settings.GDRIVE_OFFLOAD_FOLDER_ID)
    if args.lead_id:
        leads = [{"id": args.lead_id}]
    else:
        leads = await amo.get_leads(limit=min(max(args.recent, 1), 250))
    stats = {"folders": 0, "copied": 0, "skipped": 0, "errors": 0}
    for lead in leads:
        try:
            lead_id = int(lead["id"])
            await automation.ensure_lead_folder(lead_id)
            stats["folders"] += 1
            if args.stage_existing:
                result = await automation.stage_lead(lead_id)
                for key in ("copied", "skipped", "errors"):
                    stats[key] += result[key]
        except Exception:
            LOG.exception("Lead automation failed: %s", lead.get("id"))
            stats["errors"] += 1
    today = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    message = (f"Oisha CRM -> Drive | {today}\n"
               f"Papka: {stats['folders']}\n"
               f"Nusxalandi: {stats['copied']}\n"
               f"O'tkazib yuborildi: {stats['skipped']}\n"
               f"Xatolar: {stats['errors']}\n"
               f"CRM original fayllari o'chirilmadi.")
    LOG.info(message)
    if args.telegram_report:
        await asyncio.to_thread(report_telegram, message)


if __name__ == "__main__":
    asyncio.run(main())
