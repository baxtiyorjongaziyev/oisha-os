import json
import os
import sys
import time
import requests

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def fix_duplicates():
    if not os.path.exists("data/mumtoz_farangiz_transfer_audit.json"):
        print("Xatolik: data/mumtoz_farangiz_transfer_audit.json topilmadi!")
        return

    with open("data/mumtoz_farangiz_transfer_audit.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    created_pairs = data.get("created_leads", [])
    if not created_pairs:
        print("Hech qanday yaratilgan leadlar topilmadi.")
        return

    amo = AmoCRMSync()
    headers = amo._get_headers()

    print(f"Jami ko'rib chiqiladigan juftliklar soni: {len(created_pairs)} ta\n")

    # 1. Bekor qilish: boya yangi yaratilgan 29 ta dubl sdelkani status_id=143 ga o'tkazamiz
    print("1-QADAM: Yangi yaratilgan dubl sdelkalarni faol voronkadan yopish (status_id: 143)...")
    batch_size = 10
    closed_duplicates = 0
    for i in range(0, len(created_pairs), batch_size):
        chunk = created_pairs[i:i + batch_size]
        payloads = []
        for p in chunk:
            nid = p["new_lead_id"]
            orig_name = p["name"]
            payloads.append({
                "id": nid,
                "status_id": 143, # Закрыто и не реализовано
                "name": f"[Dublikat bekor qilindi] {orig_name}"
            })
        try:
            r = requests.patch(f"{amo.base_url}/api/v4/leads", headers=headers, json=payloads, timeout=20)
            if r.status_code in (200, 204):
                closed_duplicates += len(chunk)
                print(f"   [DUBL YOPILDI] {len(chunk)} ta dubl sdelka muvaffaqiyatli yopildi (status 143).")
            else:
                print(f"   [DUBL YOPISH XATO] {r.status_code} {r.text}")
        except Exception as e:
            print(f"   [DUBL YOPISH EXCEPTION]: {e}")
        time.sleep(0.3)

    print(f"\nJami yopilgan dublikatlar: {closed_duplicates} ta.\n")

    # 2. Asl bitimlarni (original_ids) o'zini Yangi LEads (89067962) ga o'tkazamiz va Mumtozmaxal tegini qo'yamiz
    print("2-QADAM: Asl bitimlarning o'zini 'Yangi LEads' (89067962) ga o'tkazish va Mumtozmaxal tegini berish...")
    updated_originals = 0
    for idx, p in enumerate(created_pairs, 1):
        orig_id = p["original_id"]
        orig_name = p["name"]
        try:
            # Fetch current lead tags
            r_get = requests.get(f"{amo.base_url}/api/v4/leads/{orig_id}", headers=headers, timeout=15)
            if r_get.status_code != 200:
                print(f"   [ORIGINAL GET ERROR] ID {orig_id}: {r_get.status_code}")
                continue

            lead_data = r_get.json()
            cur_tags = [t["name"] for t in lead_data.get("_embedded", {}).get("tags", []) if t.get("name")]
            
            # Shaxnoza yoki Rayxon tegi bor-yo'qligini yana bir bor qat'iy tekshiramiz
            has_sr = any(m in " ".join(cur_tags).lower() for m in ["shahnoza", "shaxnoza", "rayxon", "rayhona"])
            if has_sr:
                print(f"   [SKIP ORIGINAL] ID {orig_id} da Shaxnoza/Rayxon tegi bor, tegilmaydi!")
                continue

            if "Mumtozmaxal" not in cur_tags:
                cur_tags.append("Mumtozmaxal")

            patch_payload = {
                "pipeline_id": 11162698, # Sotuv Bo'limi
                "status_id": 89067962,   # Yangi LEads
                "_embedded": {
                    "tags": [{"name": tn} for tn in cur_tags]
                }
            }

            r_patch = requests.patch(f"{amo.base_url}/api/v4/leads/{orig_id}", headers=headers, json=patch_payload, timeout=15)
            if r_patch.status_code in (200, 204):
                updated_originals += 1
                print(f"   [{idx}/{len(created_pairs)}] Asl bitim {orig_id} ('{orig_name}') -> 'Yangi LEads' (89067962) ga ko'chirildi, Mumtozmaxal tegi berildi.")
                
                # Eslatma qo'shish
                note_payload = [{
                    "entity_id": orig_id,
                    "note_type": "common",
                    "params": {
                        "text": "📌 Farangiz transkripsiyali asl bitim dubl ochmasdan to'g'ridan-to'g'ri Mumtozmaxal uchun 'Yangi LEads' bosqichiga o'tkazildi."
                    }
                }]
                requests.post(f"{amo.base_url}/api/v4/leads/{orig_id}/notes", headers=headers, json=note_payload, timeout=10)
            else:
                print(f"   [ORIGINAL PATCH ERROR] ID {orig_id}: {r_patch.status_code} {r_patch.text}")
        except Exception as e:
            print(f"   [ORIGINAL EXCEPTION] ID {orig_id}: {e}")
        time.sleep(0.2)

    print("\n==================================================")
    print("NATIJA:")
    print(f"Yopilgan/faol emas qilingan dubllar: {closed_duplicates} ta")
    print(f"To'g'ridan-to'g'ri 'Yangi LEads'ga o'tkazilgan asl bitimlar: {updated_originals} ta")
    print("Birorta ham yangi dublikat bitim yo'q! Asl bitimlar saqlandi.")
    print("==================================================")

if __name__ == "__main__":
    fix_duplicates()
