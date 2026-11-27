"""CLI for unified 5-system client sync (Google, Telegram, amoCRM, Airtable, Second Brain).

Usage:
  python scripts/unified_client_sync_cli.py --dry-run --limit 20
  python scripts/unified_client_sync_cli.py --apply --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.core.client_sync.adapters_contacts import SecondBrainUnifiedAdapter
from src.services.core.client_sync.adapters_crm import (
    AmoCRMUnifiedAdapter,
    profile_from_amocrm_contact,
)
from src.services.core.client_sync.runner import run_unified_client_sync


def _load_amocrm_profiles(amo, max_pages: int = 20) -> list:
    import requests

    profiles = []
    for page in range(1, max_pages + 1):
        resp = requests.get(
            f"{amo.base_url}/api/v4/contacts",
            headers=amo._get_headers(),
            params={"page": page, "limit": 250},
            timeout=30,
        )
        if resp.status_code != 200:
            break
        batch = (resp.json().get("_embedded") or {}).get("contacts") or []
        if not batch:
            break
        for contact in batch:
            prof = profile_from_amocrm_contact(contact)
            if prof:
                profiles.append(prof)
        if len(batch) < 250:
            break
    return profiles


async def _run(dry_run: bool, limit: int | None, vault_dir: str | None) -> dict:
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.settings import settings

    secret = settings.AMOCRM_CLIENT_SECRET
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret or ""),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    profiles = _load_amocrm_profiles(amo)
    adapters = [AmoCRMUnifiedAdapter(amo)]
    if vault_dir:
        adapters.append(SecondBrainUnifiedAdapter([Path(vault_dir)]))
    report = await run_unified_client_sync(
        profiles,
        sync_adapters=adapters,
        dry_run=dry_run,
        limit=limit,
    )
    return {
        "dry_run": report.dry_run,
        "total_input": report.total_input,
        "eligible_clients": report.eligible_clients,
        "skipped_ineligible": report.skipped_ineligible,
        "per_system": report.per_system,
        "errors": report.errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="5-system unified client profile sync.")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run).")
    parser.add_argument("--limit", type=int, default=None, help="Max eligible clients to process.")
    parser.add_argument("--vault", default="", help="Optional Obsidian vault directory.")
    args = parser.parse_args()
    result = asyncio.run(_run(dry_run=not args.apply, limit=args.limit, vault_dir=args.vault or None))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
