"""Migrate all deals from [ARXIV] 2. CLOSER and [ARXIV] Target LEADs to Sotuv Bo'limi.

Moves:
- Closed Won (142) -> Sotuv Bo'limi (11162698) status 142
- Closed Lost (143) -> Sotuv Bo'limi (11162698) status 143
- Active / New (any other) -> Sotuv Bo'limi (11162698) status 87609514 (Yangi)

Ensures 0 deals remain in the archived pipelines so they can be deleted in AmoCRM.
"""
from __future__ import annotations

import json
import sys
import time
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SALES_PIPELINE_ID = 11162698
SALES_NEW_STATUS_ID = 87609514
STATUS_WON = 142
STATUS_LOST = 143

SOURCE_PIPELINES = [
    (11162702, "[ARXIV] 2. CLOSER"),
    (11295630, "[ARXIV] Target LEADs"),
]

BASE_URL = "https://jonbranding.amocrm.ru"


def get_headers() -> dict[str, str]:
    with open("data/amocrm_token.json") as f:
        token = json.load(f)["access_token"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def fetch_all_leads(pipeline_id: int, headers: dict[str, str]) -> list[dict]:
    leads: list[dict] = []
    page = 1
    while True:
        url = f"{BASE_URL}/api/v4/leads"
        params = {"filter[pipeline_id]": pipeline_id, "page": page, "limit": 250}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 204:
            break
        if r.status_code != 200:
            print(f"  Error fetching page {page} for pipeline {pipeline_id}: {r.status_code} {r.text}")
            break
        data = r.json()
        chunk = data.get("_embedded", {}).get("leads", [])
        if not chunk:
            break
        leads.extend(chunk)
        if len(chunk) < 250:
            break
        page += 1
    return leads


def batch_update_leads(updates: list[dict], headers: dict[str, str], batch_size: int = 50) -> int:
    total_updated = 0
    total = len(updates)
    for i in range(0, total, batch_size):
        batch = updates[i : i + batch_size]
        url = f"{BASE_URL}/api/v4/leads"
        r = requests.patch(url, headers=headers, json=batch, timeout=30)
        if r.status_code in (200, 204):
            total_updated += len(batch)
            print(f"  Processed {total_updated}/{total} leads...")
        else:
            print(f"  Error in batch {i // batch_size + 1}: {r.status_code} {r.text}")
        time.sleep(0.3)
    return total_updated


def main() -> None:
    headers = get_headers()
    print("=" * 60)
    print("MIGRATION: Archived Pipelines -> Sotuv Bo'limi (11162698)")
    print("=" * 60)

    all_updates: list[dict] = []

    for pid, pname in SOURCE_PIPELINES:
        leads = fetch_all_leads(pid, headers)
        print(f"\nPipeline: {pname} (ID: {pid})")
        print(f"Found {len(leads)} deals.")

        for lead in leads:
            lid = lead["id"]
            st = lead.get("status_id")
            if st == STATUS_WON:
                target_status = STATUS_WON
            elif st == STATUS_LOST:
                target_status = STATUS_LOST
            else:
                target_status = SALES_NEW_STATUS_ID

            all_updates.append(
                {
                    "id": lid,
                    "pipeline_id": SALES_PIPELINE_ID,
                    "status_id": target_status,
                }
            )

    print(f"\nTotal deals to migrate across all archived pipelines: {len(all_updates)}")
    if not all_updates:
        print("No deals found to migrate!")
        return

    print("Executing batch migration to Sotuv Bo'limi...")
    updated_count = batch_update_leads(all_updates, headers, batch_size=50)
    print(f"\nMigration finished: {updated_count}/{len(all_updates)} deals updated.")

    print("\n" + "=" * 60)
    print("VERIFICATION: Checking remaining deals in archived pipelines...")
    print("=" * 60)
    for pid, pname in SOURCE_PIPELINES:
        remaining = fetch_all_leads(pid, headers)
        print(f"Pipeline: {pname} (ID: {pid}) -> Remaining deals: {len(remaining)}")


if __name__ == "__main__":
    main()
