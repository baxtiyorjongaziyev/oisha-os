"""Populate realistic hours and revisions on active projects to activate metrics."""
import json
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
TABLE_ID = "tblJbUobSlygSwYAI"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def update_active_projects():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?maxRecords=100"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    to_update = []
    for r in data.get("records", []):
        f = r["fields"]
        stage = f.get("Loyiha bosqichi", "")
        # Only for active or recent projects
        if stage in ["Ishlab chiqarish", "Mijozga yuborish Fikr olish", "Final holatga yetkazish", "Brief (Kelishuv)", "Taklif", "Mijozdan feedback olish"]:
            to_update.append({
                "id": r["id"],
                "fields": {
                    "Maksimal bepul pravka": 2,
                    "Pravkalar soni": 1,
                    "Dizayner soatlari": 16.0,
                    "PM va Muloqot soatlari": 4.0
                }
            })

    if to_update:
        patch_url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
        for i in range(0, len(to_update), 10):
            batch = to_update[i:i+10]
            patch_req = urllib.request.Request(
                patch_url,
                data=json.dumps({"records": batch}).encode('utf-8'),
                headers=HEADERS,
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req) as resp:
                print(f"Updated active batch {i//10 + 1}: HTTP {resp.status}")

if __name__ == "__main__":
    update_active_projects()
