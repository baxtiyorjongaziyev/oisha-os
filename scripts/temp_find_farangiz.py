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

def inspect_farangiz_leads():
    with open("data/farangiz_entities_to_update.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    farangiz_leads = data.get("leads", [])
    print(f"Loaded {len(farangiz_leads)} leads from farangiz_entities_to_update.json\n")

    amo = AmoCRMSync()
    headers = amo._get_headers()

    # Let's inspect each lead:
    # 1. tags
    # 2. notes (check for 'farangiz' in transcript)
    # 3. last call timestamp
    results = []

    oct_19_start_ts = int(datetime(2026, 10, 19, 0, 0, 0).timestamp())

    for idx, item in enumerate(farangiz_leads[:30], 1): # sample first 30
        lid = item["id"]
        r = requests.get(f"{amo.base_url}/api/v4/leads/{lid}?with=contacts", headers=headers, timeout=20)
        if r.status_code != 200:
            continue
        ldata = r.json()
        tags = [t["name"] for t in ldata.get("_embedded", {}).get("tags", [])] if ldata.get("_embedded") else []
        tag_str = " ".join(tags).lower()

        has_shahnoza = "shahnoza" in tag_str or "shaxnoza" in tag_str
        has_rayxon = "rayxon" in tag_str or "rayhona" in tag_str

        # Get notes
        rn = requests.get(f"{amo.base_url}/api/v4/leads/{lid}/notes", headers=headers, timeout=20)
        notes = rn.json().get("_embedded", {}).get("notes", []) if rn.status_code == 200 else []

        farangiz_in_transcript = False
        last_call_ts = None
        call_count = 0

        for n in notes:
            text = str(n.get("params", {}).get("text") or "")
            ntype = n.get("note_type")
            created_at = n.get("created_at")

            if "farangiz" in text.lower():
                farangiz_in_transcript = True

            if ntype in ("call_in", "call_out") or "AI_CALL_ANALYSIS" in text or "Qo'ng'iroq" in text:
                call_count += 1
                if created_at and (last_call_ts is None or created_at > last_call_ts):
                    last_call_ts = created_at

        last_call_str = datetime.fromtimestamp(last_call_ts).strftime("%Y-%m-%d %H:%M") if last_call_ts else "Hech qachon"
        called_on_or_after_19th = last_call_ts is not None and last_call_ts >= oct_19_start_ts

        print(f"[{idx:2d}] ID {lid} | Name: {ldata.get('name')[:30]} | Status: {ldata.get('status_id')}")
        print(f"     Tags: {tags}")
        print(f"     Farangiz in transcript: {farangiz_in_transcript} | Calls: {call_count} | Last Call: {last_call_str} (>= 19-okt: {called_on_or_after_19th})")
        print(f"     Has Shahnoza/Rayxon tag: {has_shahnoza or has_rayxon}")

if __name__ == "__main__":
    inspect_farangiz_leads()
