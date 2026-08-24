"""Update Dilorom project with correct deposit / agreed price."""
import json
import urllib.request

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
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
