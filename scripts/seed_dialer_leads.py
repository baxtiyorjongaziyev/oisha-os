"""Seed dialer database with all active AmoCRM leads and phone numbers."""
import asyncio
import json
import logging
from pathlib import Path
import sys
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests
from src.services.core.crm.dialer_store import DialerStore
from src.services.core.crm.dialer_service import AMOCRM_TO_SLUG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_dialer")

SELLER_NAMES = {
    8128012: "Baxtiyorjon Gaziyev",
    13021974: "Shahnoza Abdijabborova",
    13838466: "Oydin Ermuhammadova",
    13841510: "Oydin Ermuhammadova",
}


def fetch_contacts_bulk(headers: dict, contact_ids: list[int]) -> dict[int, dict]:
    results = {}
    for i in range(0, len(contact_ids), 40):
        chunk = contact_ids[i:i+40]
        params = [("filter[id][]", cid) for cid in chunk]
        try:
            r = requests.get("https://jonbranding.amocrm.ru/api/v4/contacts", headers=headers, params=params, timeout=20)
            if r.status_code == 200:
                for c in r.json().get("_embedded", {}).get("contacts", []):
                    phone = None
                    for cf in c.get("custom_fields_values") or []:
                        if cf.get("field_code") == "PHONE":
                            vals = cf.get("values", [])
                            if vals:
                                phone = str(vals[0].get("value")).strip()
                    results[c["id"]] = {"name": c.get("name") or "", "phone": phone or ""}
        except Exception as exc:
            logger.warning("Error fetching contact chunk: %s", exc)
    return results


def main():
    store = DialerStore()
    token_data = json.loads(open("data/amocrm_token.json", encoding="utf-8").read())
    headers = {"Authorization": f"Bearer {token_data['access_token']}", "Content-Type": "application/json"}

    logger.info("Fetching active leads from pipeline 11162698 (Sotuv Bo'limi)...")
    page = 1
    raw_leads = []

    while True:
        url = "https://jonbranding.amocrm.ru/api/v4/leads"
        params = {"limit": 50, "page": page, "filter[pipeline_id]": 11162698, "with": "contacts"}
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            break
        items = r.json().get("_embedded", {}).get("leads", [])
        if not items:
            break
        for item in items:
            if item.get("status_id") != 143:
                raw_leads.append(item)
        if not r.json().get("_links", {}).get("next"):
            break
        page += 1

    logger.info("Found %d active leads across %d pages", len(raw_leads), page)

    # Collect contact IDs
    contact_ids = []
    for l in raw_leads:
        contacts = l.get("_embedded", {}).get("contacts", [])
        if contacts and contacts[0].get("id"):
            contact_ids.append(contacts[0]["id"])

    logger.info("Fetching details for %d unique contacts...", len(contact_ids))
    contacts_map = fetch_contacts_bulk(headers, contact_ids)
    logger.info("Resolved %d contacts with phone numbers", len(contacts_map))

    # Upsert into DialerStore
    count = 0
    for l in raw_leads:
        contacts = l.get("_embedded", {}).get("contacts", [])
        cid = contacts[0].get("id") if contacts else None
        cinfo = contacts_map.get(cid, {}) if cid else {}

        rep_id = l.get("responsible_user_id")
        rep_name = SELLER_NAMES.get(rep_id, "Sotuvchi")

        status_slug = AMOCRM_TO_SLUG.get(l.get("status_id"), "yangi")
        store.upsert_lead({
            "id": l["id"],
            "pipeline_id": 11162698,
            "name": l.get("name") or f"Bitim #{l['id']}",
            "contact_name": cinfo.get("name") or l.get("name") or "",
            "phone": cinfo.get("phone") or "",
            "price": l.get("price") or 0.0,
            "status_id": l.get("status_id") or 0,
            "status_slug": status_slug,
            "responsible_user_id": rep_id,
            "responsible_name": rep_name,
            "source": "Meta Lead Ads",
            "is_active": True,
        })
        count += 1

    logger.info("Successfully seeded %d leads into dialer database!", count)
    stats = store.get_stats()
    logger.info("Dialer Stats: %s", stats)


if __name__ == "__main__":
    main()
