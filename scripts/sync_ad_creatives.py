#!/usr/bin/env python3
"""Sync ad creatives registry and optionally backfill AmoCRM leads with creative URLs.

Usage:
    python scripts/sync_ad_creatives.py --seed
    python scripts/sync_ad_creatives.py --backfill --limit 20
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import requests

from src.services.core.instagram.leadgen_custom_fields import (
    FIELD_CREATIVE_URL,
    FIELD_CREATIVE_NAME,
    FIELD_UTM_CONTENT,
    FIELD_OPENSTAT_AD,
)
from src.services.core.marketing.ad_creative_service import (
    KNOWN_CREATIVE_URLS,
    KNOWN_CREATIVE_NAMES,
    infer_creative_type,
    resolve_ad_creative,
    save_creative,
)

sys.stdout.reconfigure(encoding="utf-8")


def seed_from_spend_db() -> int:
    """Seed all distinct ads from meta_ad_spend_by_ad into meta_ad_creatives.db."""
    spend_db = Path("data/meta_ad_spend.db")
    if not spend_db.exists():
        print(f"[!] {spend_db} not found.")
        return 0

    conn = sqlite3.connect(spend_db)
    ads = conn.execute("SELECT DISTINCT ad_id, ad_name, campaign_name FROM meta_ad_spend_by_ad").fetchall()
    count = 0
    for ad_id, ad_name, campaign_name in ads:
        if not ad_id:
            continue
        c_type, icon = infer_creative_type(ad_name)
        url = KNOWN_CREATIVE_URLS.get(ad_id)
        if not url and ad_name and ad_name.lower() in KNOWN_CREATIVE_URLS:
            url = KNOWN_CREATIVE_URLS[ad_name.lower()]
        if not url:
            url = f"https://www.facebook.com/ads/manage/preview/?ad_id={ad_id}"

        save_creative(ad_id, ad_name, url, c_type, icon, campaign_name=campaign_name)
        count += 1

    # Also seed explicit known creatives
    for k, url in KNOWN_CREATIVE_URLS.items():
        name = KNOWN_CREATIVE_NAMES.get(k) or f"Creative {k}"
        c_type, icon = infer_creative_type(name)
        save_creative(k, name, url, c_type, icon)

    print(f"[OK] Seeded {count} ads into meta_ad_creatives.db")
    return count


def backfill_amocrm_leads(limit: int = 50) -> int:
    """Backfill recent AmoCRM leads with creative URL and name fields."""
    token_file = Path("data/amocrm_token.json")
    if not token_file.exists():
        print("[!] data/amocrm_token.json not found.")
        return 0

    with open(token_file, encoding="utf-8") as f:
        token = json.load(f)["access_token"]

    attr_db = Path("data/meta_ad_attribution.db")
    if not attr_db.exists():
        print("[!] Attribution DB not found.")
        return 0

    conn = sqlite3.connect(attr_db)
    rows = conn.execute(
        "SELECT leadgen_id, lead_id, ad_id, campaign_name FROM lead_attribution "
        "WHERE lead_id IS NOT NULL ORDER BY rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    updated = 0

    for leadgen_id, lead_id, ad_id, campaign_name in rows:
        if not ad_id:
            continue
        cr = resolve_ad_creative(ad_id, campaign_name=campaign_name)
        if not cr.creative_url:
            continue

        payload = {
            "custom_fields_values": [
                {"field_id": FIELD_CREATIVE_URL, "values": [{"value": cr.creative_url}]},
                {"field_id": FIELD_CREATIVE_NAME, "values": [{"value": f"{cr.type_icon} {cr.ad_name}"}]},
                {"field_id": FIELD_UTM_CONTENT, "values": [{"value": cr.ad_name}]},
                {"field_id": FIELD_OPENSTAT_AD, "values": [{"value": str(ad_id)}]},
            ]
        }

        try:
            r = requests.patch(f"https://jonbranding.amocrm.ru/api/v4/leads/{lead_id}", headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                print(f"[OK] Lead #{lead_id}: {cr.type_icon} {cr.ad_name} -> {cr.creative_url}")
                updated += 1
            else:
                print(f"[ERR] Lead #{lead_id} status {r.status_code}: {r.text[:100]}")
        except Exception as exc:
            print(f"[EXC] Lead #{lead_id}: {exc}")

    print(f"\n[DONE] Successfully backfilled {updated}/{len(rows)} leads in AmoCRM!")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Ad Creative Sync & Backfill")
    parser.add_argument("--seed", action="store_true", help="Seed registry from spend database")
    parser.add_argument("--backfill", action="store_true", help="Backfill recent leads in AmoCRM")
    parser.add_argument("--limit", type=int, default=20, help="Number of leads to backfill")
    args = parser.parse_args()

    if not args.seed and not args.backfill:
        args.seed = True
        args.backfill = True

    if args.seed:
        seed_from_spend_db()
    if args.backfill:
        backfill_amocrm_leads(limit=args.limit)


if __name__ == "__main__":
    main()
