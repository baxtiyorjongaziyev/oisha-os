"""Update Dilorom project with correct deposit / agreed price."""
import json
import os
import urllib.request

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
TABLE_ID = "tblJbUobSlygSwYAI"
RECORD_ID = "rec9sh4UvqTWwbokh"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def update_dilorom():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}/{RECORD_ID}"
    # Set agreed price to 333 USD (~4,000,000 UZS) and update name to note deposit reservation
    payload = {
        "fields": {
            "Kelishgan narx": 333,
            "Loyihani nomi?": "Dilorom Murodovna — Naming & Logo (Joy band qilindi)"
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=HEADERS,
        method="PATCH"
    )
    with urllib.request.urlopen(req) as resp:
        print("Updated Dilorom record successfully: HTTP", resp.status)

if __name__ == "__main__":
    update_dilorom()
