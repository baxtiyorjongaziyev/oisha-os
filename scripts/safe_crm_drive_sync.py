#!/usr/bin/env python3
"""Safe existing-deal backfill and ongoing amoCRM -> Google Drive sync.

All modes are non-destructive to CRM originals.  --dry-run does no writes.
Full backfill uses pagination, while periodic --recent keeps new deals linked.
"""
from __future__ import annotations

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

LOG = logging.getLogger(__name__)
CLOSED_STATUSES = {142, 143}


def report_telegram(message: str) -> bool:
    token = settings.BOT_TOKEN.get_secret_value()
    if not token or not settings.CRM_GROUP_ID:
        LOG.warning("Telegram report not configured (BOT_TOKEN / CRM_GROUP_ID)")
        return False
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": settings.CRM_GROUP_ID, "text": message},
        timeout=20,
    )
    response.raise_for_status()
    return True


async def fetch_all_leads(
    amo: AmoCRMSync, *, page_size: int = 250, max_pages: int = 100
):
    """Yield all paginated leads. API failures raise, never imply empty CRM."""
    amo._load_token()
    seen: set[int] = set()
    for page in range(1, max_pages + 1):
        params = {"page": page, "limit": page_size, "order[created_at]": "asc"}
        response = await amo._request_with_auth(
            requests.get, f"{amo.base_url}/api/v4/leads",
            params=params, timeout=35,
        )
        if response.status_code == 401:
            refreshed = await asyncio.to_thread(amo.refresh_token)
            if not refreshed:
                raise RuntimeError("amoCRM authentication failed on backfill")
            response = await amo._request_with_auth(
                requests.get, f"{amo.base_url}/api/v4/leads",
                params=params, timeout=35,
            )
        if response.status_code == 204:
            return
        if response.status_code != 200:
            raise RuntimeError(f"amoCRM leads page={page}: HTTP {response.status_code}")
        data = response.json()
        items = data.get("_embedded", {}).get("leads")
        if not isinstance(items, list):
            raise RuntimeError(f"amoCRM leads page={page} has invalid payload")
        for lead in items:
            if not isinstance(lead, dict) or "id" not in lead:
                raise RuntimeError(f"amoCRM leads page={page} malformed lead")
            identifier = int(lead["id"])
            if identifier not in seen:
                seen.add(identifier)
                yield lead
        if len(items) < page_size:
            return
    raise RuntimeError(f"Backfill exceeded max_pages={max_pages}; incomplete scan")


async def check_drive_access(drive: GoogleDriveSync, root: str) -> dict:
    """Read-only preflight for the configured **service account**, not user OAuth."""
    def read():
        about = drive.service.about().get(fields="user(emailAddress),storageQuota").execute()
        folder = drive.service.files().get(
            fileId=root,
            supportsAllDrives=True,
            fields="id,name,mimeType,driveId,capabilities(canAddChildren),trashed",
        ).execute()
        return about, folder
    about, folder = await asyncio.to_thread(read)
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise RuntimeError("Configured Drive target is not an accessible folder")
    if not folder.get("capabilities", {}).get("canAddChildren", False):
        raise PermissionError("Google Drive account cannot add files to target folder")
    from os import environ
    expected = environ.get("GDRIVE_EXPECTED_EMAIL", "").strip().lower()
    actual = (about.get("user") or {}).get("emailAddress", "").lower()
    if expected and actual != expected:
        raise PermissionError("Drive account differs from configured personal owner")
    minimum = 4_500_000_000_000 if expected else 0
    quota_limit = int((about.get("storageQuota") or {}).get("limit") or 0)
    if minimum and quota_limit < minimum:
        raise PermissionError("5 TB Drive storage is not verified; refusing CRM upload")
    return {
        "google_account": about.get("user", {}).get("emailAddress", "unknown"),
        "folder": folder.get("name"),
        "shared_drive": bool(folder.get("driveId")),
        "can_add_children": True,
        "quota_usage": (about.get("storageQuota") or {}).get("usage"),
        "quota_limit": (about.get("storageQuota") or {}).get("limit"),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--lead-id", type=int)
    source.add_argument("--recent", type=int, help="Recent leads, max 250 (for polling)")
    source.add_argument("--all-existing", action="store_true", help="Paginated complete CRM scan")
    source.add_argument("--preflight", action="store_true", help="Read-only Drive permissions check")
    parser.add_argument("--stage-existing", action="store_true", help="Copy/verify files, never delete originals")
    parser.add_argument("--active-only", action="store_true", help="Skip won/lost leads")
    parser.add_argument("--dry-run", action="store_true", help="No CRM/Drive writes")
    parser.add_argument("--telegram-report", action="store_true")
    parser.add_argument("--probe-write", action="store_true", help="In preflight, create/remove a tiny Drive test file")
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_pages > 500:
        parser.error("--max-pages must be between 1 and 500")
    if args.probe_write and not args.preflight:
        parser.error("--probe-write requires --preflight")
    root = settings.GDRIVE_OFFLOAD_FOLDER_ID
    if not root:
        parser.error("GDRIVE_OFFLOAD_FOLDER_ID must point to an accessible Drive folder")

    # CRM migrations MUST NOT silently fall back to a service account.
    # Personal owner OAuth is mandatory even for a manual CLI run.
    import os
    from src.services.core.crm.drive_oauth_onboarding import token_path
    if not token_path().is_file():
        parser.error("Personal Google Drive OAuth consent missing; refusing migration")
    os.environ["GDRIVE_AUTH_MODE"] = "oauth"
    drive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
    preflight = await check_drive_access(drive, root)
    LOG.info("Drive service-account preflight: %s", preflight)
    if args.preflight:
        if args.probe_write:
            from googleapiclient.http import MediaIoBaseUpload
            import io
            import secrets

            def probe():
                marker = f"oisha-drive-probe-{secrets.token_hex(6)}.txt"
                created = drive.service.files().create(
                    body={"name": marker, "parents": [root]},
                    media_body=MediaIoBaseUpload(
                        io.BytesIO(b"Oisha write probe"), mimetype="text/plain"
                    ),
                    fields="id,size", supportsAllDrives=True,
                ).execute()
                try:
                    if int(created.get("size", -1)) != len(b"Oisha write probe"):
                        raise RuntimeError("Drive probe uploaded an unexpected size")
                finally:
                    drive.service.files().delete(
                        fileId=created["id"], supportsAllDrives=True
                    ).execute()
                return True
            await asyncio.to_thread(probe)
            LOG.info("Drive create/readback/delete probe passed")
        return

    amo = AmoCRMSync()
    automation = SafeCRMDriveAutomation(amo, drive, root)
    stats = {"scanned": 0, "folders": 0, "files_found": 0,
             "copied": 0, "skipped": 0, "errors": 0}

    async def process(lead: dict) -> None:
        identifier = int(lead["id"])
        if args.active_only and int(lead.get("status_id") or 0) in CLOSED_STATUSES:
            return
        stats["scanned"] += 1
        try:
            if args.dry_run:
                if args.stage_existing:
                    notes = await amo.get_lead_notes(identifier)
                    if amo.last_error:
                        raise RuntimeError(f"CRM notes unavailable: {amo.last_error}")
                    stats["files_found"] += sum(n.get("note_type") == "file" for n in notes)
                return
            await automation.ensure_lead_folder(identifier)
            stats["folders"] += 1
            if args.stage_existing:
                result = await automation.stage_lead(identifier)
                for key in ("copied", "skipped", "errors"):
                    stats[key] += result[key]
        except Exception:
            LOG.exception("Lead sync failed: %s", identifier)
            stats["errors"] += 1

    try:
        if args.lead_id:
            lead = await amo.get_lead(args.lead_id)
            if not lead:
                raise RuntimeError(f"Lead {args.lead_id} not found or inaccessible")
            await process(lead)
        elif args.recent:
            if not 1 <= args.recent <= 250:
                parser.error("--recent must be between 1 and 250")
            recent = await amo.get_leads(
                limit=args.recent, **{"order[created_at]": "desc"}
            )
            if amo.last_error:
                raise RuntimeError(f"amoCRM recent list unavailable: {amo.last_error}")
            for lead in recent:
                await process(lead)
        else:
            async for lead in fetch_all_leads(amo, max_pages=args.max_pages):
                await process(lead)
    except Exception:
        stats["errors"] += 1
        LOG.exception("CRM scan stopped before completion")

    today = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    mode = "DRY RUN" if args.dry_run else ("COPY" if args.stage_existing else "FOLDER SYNC")
    message = (
        f"Oisha CRM / Drive | {today} | {mode}\n"
        f"Tekshirilgan bitimlar: {stats['scanned']}\n"
        f"Papka bogʼlangan: {stats['folders']}\n"
        f"Fayllar koʼrilgan: {stats['files_found']}\n"
        f"Nusxalangan: {stats['copied']}\n"
        f"Oldin ishlangan: {stats['skipped']}\n"
        f"Xatolar: {stats['errors']}\n"
        "Original CRM fayllari oʼchirilmadi."
    )
    LOG.info(message)
    if args.telegram_report:
        await asyncio.to_thread(report_telegram, message)
    if stats["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
