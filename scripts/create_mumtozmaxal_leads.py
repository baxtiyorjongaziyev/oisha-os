"""
AmoCRM: Shaxnoza yoki Rayxon teglari qo'yilmagan, sotuvga eng yaqin (Kelishuv / Yopish)
2026-yil sentyabr-oktyabr oylaridagi leadlarni 'Mumtozmaxal' tegi bilan 'Yangi LEads'
bosqichiga yangi leadlar sifatida tushirish skripti.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

SALES_PIPELINE_ID = 11162698
STATUS_KELISHUV_YOPISH = 88871066
STATUS_YANGI_LEADS = 89067962
MUMTOZMAXAL_TAG = "Mumtozmaxal"


def get_target_leads(amo: AmoCRMSync) -> List[Dict[str, Any]]:
    headers = amo._get_headers()
    url = f"{amo.base_url}/api/v4/leads"

    params = {
        "filter[statuses][0][pipeline_id]": SALES_PIPELINE_ID,
        "filter[statuses][0][status_id]": STATUS_KELISHUV_YOPISH,
        "limit": 250,
        "with": "contacts",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    leads = resp.json().get("_embedded", {}).get("leads", []) if resp.status_code == 200 else []

    sept_1_2026_ts = int(datetime(2026, 9, 1).timestamp())
    eligible = []

    for l in leads:
        tags = [t["name"] for t in l.get("_embedded", {}).get("tags", [])] if l.get("_embedded") else []
        tag_str = " ".join(tags).lower()
        if any(m in tag_str for m in ["shaxnoza", "shahnoza", "rayxon", "rayhona", "mumtozmaxal"]):
            continue
        if l.get("created_at", 0) >= sept_1_2026_ts:
            eligible.append(l)

    # Sort descending by created_at
    eligible.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return eligible


def prepare_lead_payload(orig_lead: Dict[str, Any]) -> Dict[str, Any]:
    name = orig_lead.get("name") or "Yangi lead"
    price = orig_lead.get("price") or 0

    contacts = orig_lead.get("_embedded", {}).get("contacts", [])
    contact_ids = [{"id": c["id"]} for c in contacts if "id" in c]

    original_tags = [t["name"] for t in orig_lead.get("_embedded", {}).get("tags", [])] if orig_lead.get("_embedded") else []
    new_tags = [MUMTOZMAXAL_TAG]
    for t in original_tags:
        if t not in new_tags and t.lower() not in ["shaxnoza", "shahnoza", "rayxon", "rayhona"]:
            new_tags.append(t)

    payload: Dict[str, Any] = {
        "name": name,
        "price": price,
        "pipeline_id": SALES_PIPELINE_ID,
        "status_id": STATUS_YANGI_LEADS,
        "_embedded": {
            "tags": [{"name": t} for t in new_tags]
        }
    }
    if contact_ids:
        payload["_embedded"]["contacts"] = contact_ids

    # Copy clean custom fields if available
    raw_cfs = orig_lead.get("custom_fields_values") or []
    cleaned_cfs = []
    for cf in raw_cfs:
        fid = cf.get("field_id")
        vals = cf.get("values")
        if fid and vals:
            cleaned_cfs.append({
                "field_id": fid,
                "values": [{"value": v.get("value")} for v in vals if "value" in v]
            })
    if cleaned_cfs:
        payload["custom_fields_values"] = cleaned_cfs

    return payload


def create_new_leads(dry_run: bool = False):
    amo = AmoCRMSync()
    headers = amo._get_headers()
    target_leads = get_target_leads(amo)

    print(f"Tanlangan bitimlar soni: {len(target_leads)} ta.")
    if not target_leads:
        print("Tushiriladigan mos bitimlar topilmadi.")
        return

    audit_records = []
    success_count = 0
    fail_count = 0

    # Dedup by contact to prevent creating duplicates if multiple deals exist for the same contact
    seen_contacts = set()

    for idx, orig in enumerate(target_leads, 1):
        orig_id = orig.get("id")
        orig_name = orig.get("name")
        contacts = orig.get("_embedded", {}).get("contacts", [])
        c_ids = [c["id"] for c in contacts]
        primary_c_id = c_ids[0] if c_ids else None

        if primary_c_id and primary_c_id in seen_contacts:
            print(f"[{idx}/{len(target_leads)}] SKIP: Kontakt #{primary_c_id} allaqachon ko'rildi (orig deal #{orig_id}).")
            continue
        if primary_c_id:
            seen_contacts.add(primary_c_id)

        payload = prepare_lead_payload(orig)
        print(f"\n[{idx}/{len(target_leads)}] Bitim #{orig_id} -> Yangi bitim tayyorlanmoqda:")
        print(f"   Nomi: {payload['name']}")
        print(f"   Narxi: {payload['price']}")
        print(f"   Kontakt: {c_ids}")
        print(f"   Teglar: {[t['name'] for t in payload['_embedded']['tags']]}")

        if dry_run:
            print("   [DRY-RUN] Bitim yaratish simulyatsiya qilindi.")
            audit_records.append({
                "original_lead_id": orig_id,
                "new_lead_id": "dry_run",
                "name": orig_name,
                "status": "dry_run"
            })
            continue

        url = f"{amo.base_url}/api/v4/leads"
        try:
            resp = requests.post(url, headers=headers, json=[payload], timeout=30)
            if resp.status_code in (200, 201):
                new_lead = resp.json().get("_embedded", {}).get("leads", [{}])[0]
                new_id = new_lead.get("id")
                print(f"   >>> MUVAFFAQITYATLI YARATILDI! Yangi Lead ID: {new_id}")
                success_count += 1

                # Note qo'shish
                note_text = (
                    f"Oisha: Ushbu bitim asl bitim #{orig_id} ('Kelishuv / Yopish' bosqichida bo'lgan) "
                    f"asosida 'Mumtozmaxal' uchun 'Yangi LEads' bosqichiga yangi lead sifatida tushirildi."
                )
                note_url = f"{amo.base_url}/api/v4/leads/{new_id}/notes"
                note_payload = [{"note_type": "common", "params": {"text": note_text}}]
                requests.post(note_url, headers=headers, json=note_payload, timeout=15)

                audit_records.append({
                    "original_lead_id": orig_id,
                    "new_lead_id": new_id,
                    "name": orig_name,
                    "price": payload["price"],
                    "contact_ids": c_ids,
                    "tags": [t["name"] for t in payload["_embedded"]["tags"]],
                    "created_at": datetime.now().isoformat(),
                    "status": "created"
                })
            elif resp.status_code == 400 and "custom_fields_values" in payload:
                # Custom fields fallback
                fallback = dict(payload)
                fallback.pop("custom_fields_values", None)
                retry_resp = requests.post(url, headers=headers, json=[fallback], timeout=30)
                if retry_resp.status_code in (200, 201):
                    new_lead = retry_resp.json().get("_embedded", {}).get("leads", [{}])[0]
                    new_id = new_lead.get("id")
                    print(f"   >>> FALLBACK BILAN YARATILDI! Yangi Lead ID: {new_id}")
                    success_count += 1
                    note_text = (
                        f"Oisha: Ushbu bitim asl bitim #{orig_id} asosida 'Mumtozmaxal' uchun "
                        f"'Yangi LEads' bosqichiga yangi lead sifatida tushirildi."
                    )
                    note_url = f"{amo.base_url}/api/v4/leads/{new_id}/notes"
                    note_payload = [{"note_type": "common", "params": {"text": note_text}}]
                    requests.post(note_url, headers=headers, json=note_payload, timeout=15)
                    audit_records.append({
                        "original_lead_id": orig_id,
                        "new_lead_id": new_id,
                        "name": orig_name,
                        "status": "created_fallback"
                    })
                else:
                    print(f"   [XATO] Fallback yuborishda xato: {retry_resp.status_code} {retry_resp.text}")
                    fail_count += 1
            else:
                print(f"   [XATO] Bitim yaratishda xato: {resp.status_code} {resp.text}")
                fail_count += 1
        except Exception as e:
            print(f"   [EXCEPTION] {e}")
            fail_count += 1

        time.sleep(0.3)  # AmoCRM rate limit protection

    os.makedirs("data", exist_ok=True)
    audit_file = "data/mumtozmaxal_new_leads_audit.json"
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit_records, f, ensure_ascii=False, indent=2)

    print("\n===============================")
    print(f"JAMI NATIJA:")
    print(f"Muvaffaqiyatli yaratildi: {success_count} ta")
    print(f"Xatoliklar: {fail_count} ta")
    print(f"Audit fayli: {audit_file}")
    print("===============================\n")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    create_new_leads(dry_run=dry)
