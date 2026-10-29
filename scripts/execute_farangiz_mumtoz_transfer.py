import json
import os
import sys
import time
import requests
from datetime import datetime

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def execute_transfer():
    if not os.path.exists("data/farangiz_audit_intermediate.json"):
        print("Xatolik: data/farangiz_audit_intermediate.json topilmadi!")
        return

    with open("data/farangiz_audit_intermediate.json", "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    amo = AmoCRMSync()
    headers = amo._get_headers()

    need_tags = audit_data.get("need_mumtozmaxal_tag", [])
    eligible_new = audit_data.get("eligible_for_new_lead", [])
    skipped_sr = audit_data.get("skipped_shahnoza_rayxon", [])

    print(f"==================================================")
    print(f"IJRO BOSQICHI BOSHLANDI:")
    print(f"1. Shaxnoza yoki Rayxon tegi borligi uchun TEGILMAYDIGAN: {len(skipped_sr)} ta")
    for s in skipped_sr:
        print(f"   - [SKIP] ID: {s['id']} | {s['name']} | Teglar: {s.get('tags')}")

    print(f"\n2. Mumtozmaxal tegi qo'shiladigan mavjud bitimlar: {len(need_tags)} ta")
    print(f"3. 19-sanagacha qo'ng'iroq qilinmagan (Yangi lead qilib tushiriladigan): {len(eligible_new)} ta")
    print(f"==================================================\n")

    # 1. Update tags on existing leads
    updated_tags_count = 0
    tag_errors = 0
    for item in need_tags:
        lid = item["id"]
        try:
            r = requests.get(f"{amo.base_url}/api/v4/leads/{lid}", headers=headers, timeout=15)
            if r.status_code == 200:
                cur_data = r.json()
                cur_tags = cur_data.get("_embedded", {}).get("tags", [])
                tag_names = [t["name"] for t in cur_tags if t.get("name")]
                if "Mumtozmaxal" not in tag_names:
                    tag_names.append("Mumtozmaxal")
                    payload = {
                        "_embedded": {
                            "tags": [{"name": tn} for tn in tag_names]
                        }
                    }
                    r_patch = requests.patch(f"{amo.base_url}/api/v4/leads/{lid}", headers=headers, json=payload, timeout=15)
                    if r_patch.status_code in (200, 204):
                        updated_tags_count += 1
                        print(f"[TAG UPDATED] Lead ID {lid} ({item.get('name')}) -> Mumtozmaxal qo'shildi")
                    else:
                        tag_errors += 1
                        print(f"[TAG ERROR] Lead ID {lid}: {r_patch.status_code} {r_patch.text}")
                else:
                    print(f"[TAG SKIP] Lead ID {lid} da allaqachon Mumtozmaxal tegi bor")
        except Exception as e:
            tag_errors += 1
            print(f"[TAG EXCEPTION] Lead ID {lid}: {e}")
        time.sleep(0.2)

    # 2. Create new leads in batches of 10
    created_new_leads = []
    create_errors = 0

    batch_size = 10
    for i in range(0, len(eligible_new), batch_size):
        chunk = eligible_new[i:i + batch_size]
        payloads = []
        for item in chunk:
            name = item.get("name", "Nomsiz bitim")
            contacts = item.get("contacts", [])
            lead_obj = {
                "name": f"Mumtozmaxal - {name}",
                "pipeline_id": 11162698,
                "status_id": 89067962,
                "_embedded": {
                    "tags": [
                        {"name": "Mumtozmaxal"},
                        {"name": "Farangiz_baza"}
                    ]
                }
            }
            if contacts:
                lead_obj["_embedded"]["contacts"] = [{"id": cid} for cid in contacts]
            payloads.append(lead_obj)

        try:
            r_post = requests.post(f"{amo.base_url}/api/v4/leads", headers=headers, json=payloads, timeout=25)
            if r_post.status_code in (200, 201):
                res_leads = r_post.json().get("_embedded", {}).get("leads", [])
                for idx, created_item in enumerate(res_leads):
                    orig_item = chunk[idx]
                    nid = created_item.get("id")
                    created_new_leads.append({
                        "original_id": orig_item["id"],
                        "new_lead_id": nid,
                        "name": orig_item["name"],
                        "last_call": orig_item.get("last_call", "Hech qachon")
                    })
                    print(f"[NEW LEAD CREATED] Asl: {orig_item['id']} -> Yangi Lead ID: {nid} ('Mumtozmaxal - {orig_item['name']}')")

                    # Add explanatory note
                    note_payload = [{
                        "entity_id": nid,
                        "note_type": "common",
                        "params": {
                            "text": f"📋 Farangiz transkripsiyali bazasidan tiklandi.\n"
                                    f"Asl bitim ID: {orig_item['id']}\n"
                                    f"Oxirgi qo'ng'iroq: {orig_item.get('last_call', 'Hech qachon')}\n"
                                    f"Mas'ul teg: Mumtozmaxal"
                        }
                    }]
                    requests.post(f"{amo.base_url}/api/v4/leads/{nid}/notes", headers=headers, json=note_payload, timeout=10)
            else:
                create_errors += len(chunk)
                print(f"[BATCH CREATE ERROR] Status: {r_post.status_code} {r_post.text}")
        except Exception as e:
            create_errors += len(chunk)
            print(f"[BATCH EXCEPTION]: {e}")
        time.sleep(0.3)

    print("\n==================================================")
    print("YAKUNIY NATIJA:")
    print(f"Mavjud bitimlarga 'Mumtozmaxal' tegi qo'shildi: {updated_tags_count} ta")
    print(f"19-oktyabrgacha telefon qilinmaganlardan 'Yangi LEads' ga tushirildi: {len(created_new_leads)} ta")
    print(f"Xatoliklar: Tegda {tag_errors} ta, Yangi leadda {create_errors} ta")
    print("==================================================")

    final_audit = {
        "executed_at": datetime.now().isoformat(),
        "tags_updated_count": updated_tags_count,
        "new_leads_created_count": len(created_new_leads),
        "skipped_shahnoza_rayxon_count": len(skipped_sr),
        "skipped_leads": skipped_sr,
        "created_leads": created_new_leads
    }
    with open("data/mumtoz_farangiz_transfer_audit.json", "w", encoding="utf-8") as f:
        json.dump(final_audit, f, ensure_ascii=False, indent=2)
    print("Hisobot data/mumtoz_farangiz_transfer_audit.json ga saqlandi.")

if __name__ == "__main__":
    execute_transfer()
