"""Read-only amoCRM probe for DailyPriority seller ownership.

Reads amoCRM custom-field metadata and sales-stage leads. Never changes CRM,
Telegram, or production config. Client data is not printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.amocrm_task_cleanup import AmoCRMTaskCleaner  # noqa: E402
from src.services.core.daily_priority.gatherer import SALES_STAGES  # noqa: E402
from src.services.core.daily_priority.ownership import (  # noqa: E402
    SELLER_FIELD_NAMES, _norm, resolve_seller_key,
)
from src.services.core.daily_priority.team import ROLE_SALES, get_team  # noqa: E402

PAGE_SIZE = 250


def _field_metadata(client: AmoCRMTaskCleaner) -> list[dict]:
    fields: list[dict] = []
    for page in range(1, 11):
        data = client._get(
            "/api/v4/leads/custom_fields",
            {"page": page, "limit": PAGE_SIZE},
        )
        batch = (data.get("_embedded") or {}).get("custom_fields") or []
        for field in batch:
            if _norm(field.get("name")) in SELLER_FIELD_NAMES:
                fields.append({"id": int(field["id"]), "name": field["name"]})
        if len(batch) < PAGE_SIZE:
            return fields
    raise RuntimeError("Custom-field metadata exceeded 10 pages; aborting probe")


def _stage_leads(client: AmoCRMTaskCleaner, pipeline_id: int, status_id: int,
                 max_pages: int) -> tuple[list[dict], bool]:
    result: list[dict] = []
    for page in range(1, max_pages + 1):
        data = client._get(
            "/api/v4/leads",
            {
                "page": page,
                "limit": PAGE_SIZE,
                "filter[statuses][0][pipeline_id]": pipeline_id,
                "filter[statuses][0][status_id]": status_id,
            },
        )
        batch = (data.get("_embedded") or {}).get("leads") or []
        result.extend(
            lead for lead in batch
            if int(lead.get("status_id") or 0) == status_id
            and int(lead.get("pipeline_id") or 0) == pipeline_id
        )
        if len(batch) < PAGE_SIZE:
            return result, False
    return result, True


def probe(max_pages: int) -> dict:
    client = AmoCRMTaskCleaner(live=False)
    fields = _field_metadata(client)
    if not fields:
        raise RuntimeError("No verified Menejer/Sotuvchi custom field metadata")

    original_env = os.environ.get("DAILY_PRIORITY_SELLER_FIELD_IDS")
    ids = ",".join(str(item["id"]) for item in fields)
    os.environ["DAILY_PRIORITY_SELLER_FIELD_IDS"] = ids
    try:
        sellers = [m for m in get_team() if m.get("role") == ROLE_SALES]
        if not sellers:
            raise RuntimeError("No sellers configured; cannot verify routing")
        output: list[dict] = []
        seen: set[int] = set()
        totals = Counter()
        for pipeline_id, status_id, name in SALES_STAGES:
            leads, truncated = _stage_leads(client, pipeline_id, status_id, max_pages)
            counts = Counter()
            for lead in leads:
                try:
                    lead_id = int(lead["id"])
                except (TypeError, ValueError, KeyError):
                    counts["unassigned"] += 1
                    continue
                if lead_id in seen:
                    continue
                seen.add(lead_id)
                owner = resolve_seller_key(lead, sellers)
                counts[owner or "unassigned"] += 1
                totals[owner or "unassigned"] += 1
            output.append({
                "pipeline_id": pipeline_id,
                "status_id": status_id,
                "stage": name,
                "scanned": sum(counts.values()),
                "truncated": truncated,
                "assigned_by_seller": {
                    s["key"]: counts.get(s["key"], 0) for s in sellers
                },
                "unassigned_or_conflicting": counts.get("unassigned", 0),
            })
        return {
            "mode": "READ_ONLY",
            "crm_mutations": 0,
            "telegram_messages": 0,
            "verified_seller_fields": fields,
            "suggested_env_field_ids": ids,
            "total_unique_leads_scanned": len(seen),
            "verified_seller_leads": {s["key"]: totals.get(s["key"], 0) for s in sellers},
            "unassigned_or_conflicting": totals.get("unassigned", 0),
            "stages": output,
        }
    finally:
        if original_env is None:
            os.environ.pop("DAILY_PRIORITY_SELLER_FIELD_IDS", None)
        else:
            os.environ["DAILY_PRIORITY_SELLER_FIELD_IDS"] = original_env


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 20:
        parser.error("--max-pages must be between 1 and 20")
    result = probe(args.max_pages)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not any(item["truncated"] for item in result["stages"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
