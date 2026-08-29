"""Audit payments for stopped/zombie projects and mark fully paid ones as Yakunlangan."""
import json
import os
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
TABLE_ID = "tblJbUobSlygSwYAI"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def audit_and_fix_paid_zombies():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?maxRecords=100"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    to_complete = []
    to_keep_stopped = []

    for r in data.get("records", []):
        f = r["fields"]
        name = f.get("Loyihani nomi?", "")
        stage = f.get("Loyiha bosqichi", "")

        if stage in ["To'xtatilgan", "Vaqtinchalik to'xtatilgan"]:
            qoldiq_uzs = f.get("Qoldiq to‘lov uzs", 0)
            qoldiq_usd = f.get("Qoldiq to‘lov $", 0)
            narx_uzs = f.get("Jami loyiha narxi (UZS)", 0) or 0
            narx_usd = f.get("Jami loyiha narxi (USD)", 0) or 0
            tolangan_uzs = f.get("Jami to‘langan (UZS)", 0) or 0
            tolangan_usd = f.get("Jami to‘langan USD", 0) or 0

            # Check if project was paid (Qoldiq <= 0 and has received payment, or 0 debt)
            is_fully_paid = False
            if (qoldiq_uzs is not None and qoldiq_uzs <= 0) and (qoldiq_usd is None or qoldiq_usd <= 0):
                is_fully_paid = True
            elif (narx_uzs > 0 and tolangan_uzs >= narx_uzs) or (narx_usd > 0 and tolangan_usd >= narx_usd):
                is_fully_paid = True

            if is_fully_paid:
                to_complete.append({
                    "id": r["id"],
                    "fields": {
                        "Loyiha bosqichi": "Yakunlangan"
                    },
                    "name": name,
                    "qoldiq": f"{qoldiq_uzs} UZS / {qoldiq_usd} $"
                })
            else:
                to_keep_stopped.append({
                    "name": name,
                    "qoldiq": f"{qoldiq_uzs} UZS / {qoldiq_usd} $"
                })

    print(f"=== FULLY PAID PROJECTS TO SET AS 'Yakunlangan' ({len(to_complete)}) ===")
    for item in to_complete:
        print(f"  [OK] {item['name'][:40]:40} | Qoldiq: {item['qoldiq']}")

    print(f"\n=== UNPAID PROJECTS REMAINING 'To'xtatilgan' ({len(to_keep_stopped)}) ===")
    for item in to_keep_stopped:
        print(f"  [STOP] {item['name'][:40]:40} | Qoldiq: {item['qoldiq']}")

    # Apply update in batches of 10
    if to_complete:
        patch_records = [{"id": x["id"], "fields": x["fields"]} for x in to_complete]
        patch_url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
        for i in range(0, len(patch_records), 10):
            batch = patch_records[i:i+10]
            payload = {"records": batch}
            patch_req = urllib.request.Request(
                patch_url,
                data=json.dumps(payload).encode('utf-8'),
                headers=HEADERS,
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req) as resp:
                print(f"Updated batch {i//10 + 1} to 'Yakunlangan': HTTP {resp.status}")

if __name__ == "__main__":
    audit_and_fix_paid_zombies()
