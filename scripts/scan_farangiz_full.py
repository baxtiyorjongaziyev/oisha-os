import json
import os
import re
import sys
import requests
from datetime import datetime

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.crm.amocrm.sync import AmoCRMSync

def run_analysis():
    amo = AmoCRMSync()
    headers = amo._get_headers()

    # 1. Load the 89 known farangiz leads
    with open("data/farangiz_entities_to_update.json", "r", encoding="utf-8") as f:
        known_data = json.load(f)
    known_lead_ids = [item["id"] for item in known_data.get("leads", [])]
    print(f"Boshlang'ich Farangiz bazasida {len(known_lead_ids)} ta bitim mavjud.")

    # 2. Also fetch active leads from Sotuv Bo'limi (11162698)
    url = f"{amo.base_url}/api/v4/leads"
    params = {"filter[pipeline_id]": 11162698, "limit": 250, "with": "contacts"}
    r = requests.get(url, headers=headers, params=params)
    active_leads = r.json().get("_embedded", {}).get("leads", []) if r.status_code == 200 else []
    all_candidate_ids = list(dict.fromkeys(known_lead_ids + [l["id"] for l in active_leads]))
    print(f"Jami tekshiriladigan bitimlar (Farangiz + Sotuv aktiv): {len(all_candidate_ids)} ta\n")

    oct_19_start_ts = int(datetime(2026, 10, 19, 0, 0, 0).timestamp())

    farangiz_in_transcript = []
    skipped_shahnoza_rayxon = []
    need_mumtozmaxal_tag = []
    already_has_mumtozmaxal = []
    eligible_for_new_lead = []

    for idx, lid in enumerate(all_candidate_ids, 1):
        r_lead = requests.get(f"{amo.base_url}/api/v4/leads/{lid}?with=contacts", headers=headers, timeout=20)
        if r_lead.status_code != 200:
            continue
        ldata = r_lead.json()
        tags = [t["name"] for t in ldata.get("_embedded", {}).get("tags", [])] if ldata.get("_embedded") else []
        tag_str = " ".join(tags).lower()

        # Check notes
        r_notes = requests.get(f"{amo.base_url}/api/v4/leads/{lid}/notes", headers=headers, timeout=20)
        notes = r_notes.json().get("_embedded", {}).get("notes", []) if r_notes.status_code == 200 else []

        has_farangiz_transcript = False
        last_call_ts = None
        call_count = 0

        for n in notes:
            text = str(n.get("params", {}).get("text") or "")
            ntype = n.get("note_type")
            created_at = n.get("created_at")

            if "farangiz" in text.lower():
                has_farangiz_transcript = True

            if ntype in ("call_in", "call_out") or "[AI_CALL_ANALYSIS]" in text or "Qo'ng'iroq" in text:
                call_count += 1
                if created_at and (last_call_ts is None or created_at > last_call_ts):
                    last_call_ts = created_at

        # Agar transkripsiyada Farangiz bo'lsa (yoki taglarida farangiz bo'lgan bo'lsa)
        if not has_farangiz_transcript:
            continue

        farangiz_in_transcript.append(ldata)

        # Qoida 1: Agar Shaxnoza yoki Rayxon teglari bor bo'lsa tegma
        has_sr = any(m in tag_str for m in ["shahnoza", "shaxnoza", "rayxon", "rayhona"])
        if has_sr:
            skipped_shahnoza_rayxon.append({
                "lead": ldata,
                "tags": tags,
                "reason": "Shaxnoza yoki Rayxon tegi bor"
            })
            continue

        # Qoida 2: Qolganini Mumtozmaxal tegiga o'tkazib ber
        has_mumtoz = "mumtozmaxal" in tag_str
        if not has_mumtoz:
            need_mumtozmaxal_tag.append(ldata)
        else:
            already_has_mumtozmaxal.append(ldata)

        # Qoida 3: 19-sanagacha telefon qilinmaganlarini yangi leadga tushirib ber
        called_on_or_after_19th = last_call_ts is not None and last_call_ts >= oct_19_start_ts
        if not called_on_or_after_19th:
            eligible_for_new_lead.append({
                "lead": ldata,
                "tags": tags,
                "last_call_ts": last_call_ts,
                "call_count": call_count
            })

    print("==================================================")
    print("TAHLIL NATIJASI:")
    print(f"1. Transkripsiyasida 'Farangiz' topilgan jami bitimlar: {len(farangiz_in_transcript)} ta")
    print(f"2. Shaxnoza yoki Rayxon tegi borligi uchun TEGILMAYDIGAN: {len(skipped_shahnoza_rayxon)} ta")
    print(f"3. Mumtozmaxal tegiga o'tkazilishi kerak bo'lgan: {len(need_mumtozmaxal_tag)} ta")
    print(f"   (Allaqachon Mumtozmaxal tegi bor: {len(already_has_mumtozmaxal)} ta)")
    print(f"4. 19-sanagacha telefon qilinmagan (Yangi lead qilib tushiriladigan): {len(eligible_for_new_lead)} ta")
    print("==================================================")

    # Save detailed intermediate data
    with open("data/farangiz_audit_intermediate.json", "w", encoding="utf-8") as f:
        json.dump({
            "total_farangiz_transcript": len(farangiz_in_transcript),
            "skipped_shahnoza_rayxon": [{"id": x["lead"]["id"], "name": x["lead"]["name"], "tags": x["tags"]} for x in skipped_shahnoza_rayxon],
            "need_mumtozmaxal_tag": [{"id": x["id"], "name": x["name"]} for x in need_mumtozmaxal_tag],
            "already_has_mumtozmaxal": [{"id": x["id"], "name": x["name"]} for x in already_has_mumtozmaxal],
            "eligible_for_new_lead": [
                {
                    "id": x["lead"]["id"],
                    "name": x["lead"]["name"],
                    "contacts": [c["id"] for c in x["lead"].get("_embedded", {}).get("contacts", [])],
                    "call_count": x["call_count"],
                    "last_call": datetime.fromtimestamp(x["last_call_ts"]).strftime("%Y-%m-%d %H:%M") if x["last_call_ts"] else "Hech qachon"
                }
                for x in eligible_for_new_lead
            ]
        }, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run_analysis()
