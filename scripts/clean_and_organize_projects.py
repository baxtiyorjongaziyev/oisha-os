"""Clean and organize legacy projects in Airtable Loyihalar table."""
import json
import urllib.request
import urllib.parse

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
TABLE_ID = "tblJbUobSlygSwYAI"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def clean_legacy_projects():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?maxRecords=100"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    to_archive = []
    for r in data.get("records", []):
        f = r["fields"]
        stage = f.get("Loyiha bosqichi", "")
        start = str(f.get("Start sana", ""))
        end = str(f.get("END sana", ""))
        name = f.get("Loyihani nomi?", "")

        # Only touch if not already finished or stopped
        if stage not in ["Yakunlangan", "To'xtatilgan", "Vaqtinchalik to'xtatilgan"]:
            # If from 2025 or earlier
            if start.startswith("2025") or end.startswith("2025") or (end and end < "2026-03-01"):
                to_archive.append({
                    "id": r["id"],
                    "fields": {
                        "Loyiha bosqichi": "To'xtatilgan"
                    }
                })
                print(f"Archiving: {name} (Dates: {start} -> {end}, Stage: {stage})")

    print(f"Total projects to archive: {len(to_archive)}")

    # Update in batches of 10
    patch_url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
    for i in range(0, len(to_archive), 10):
        batch = to_archive[i:i+10]
        payload = {"records": batch}
        patch_req = urllib.request.Request(
            patch_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=HEADERS,
            method="PATCH"
        )
        with urllib.request.urlopen(patch_req) as resp:
            print(f"Archived batch {i//10 + 1}: HTTP {resp.status}")

if __name__ == "__main__":
    clean_legacy_projects()
