"""Fix Financial Terminology in Airtable Loyihalar table:
Correct Gross Profit (Yalpi Foyda) vs Net Profit (Sof Foyda).
"""
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

def get_fields():
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        for t in data.get('tables', []):
            if t['id'] == TABLE_ID:
                return {f['name']: f['id'] for f in t.get('fields', [])}
    return {}

def update_field(field_id, payload):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields/{field_id}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=HEADERS,
        method="PATCH"
    )
    with urllib.request.urlopen(req) as resp:
        print(f"Updated field {field_id}: HTTP {resp.status}")

def create_field(payload):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=HEADERS
    )
    with urllib.request.urlopen(req) as resp:
        print(f"Created field '{payload['name']}': HTTP {resp.status}")

if __name__ == "__main__":
    fields = get_fields()
    print("Found fields:", len(fields))

    # 1. Rename 'Haqiqiy Sof Foyda (UZS)' -> 'Loyiha Yalpi Foydasi (Gross Profit UZS)'
    if "Haqiqiy Sof Foyda (UZS)" in fields:
        fid = fields["Haqiqiy Sof Foyda (UZS)"]
        update_field(fid, {
            "name": "Loyiha Yalpi Foydasi (UZS)"
        })

    # 2. Rename 'Haqiqiy Rentabellik (%)' -> 'Loyiha Yalpi Marjasi (Gross Margin %)'
    if "Haqiqiy Rentabellik (%)" in fields:
        fid = fields["Haqiqiy Rentabellik (%)"]
        update_field(fid, {
            "name": "Loyiha Yalpi Marjasi (%)"
        })

    # 3. Rename 'Loyiha Rentabellik Holati' -> 'Loyiha Marja Holati'
    if "Loyiha Rentabellik Holati" in fields:
        fid = fields["Loyiha Rentabellik Holati"]
        update_field(fid, {
            "name": "Loyiha Marja Holati",
            "options": {
                "formula": "IF({Loyiha Yalpi Foydasi (UZS)} < 0, '🔴 ZARARDA (Minus)', IF({Loyiha Yalpi Marjasi (%)} < 0.5, '🟡 O‘rtacha marja (<50%)', '🟢 Yuqori marja (>=50%)'))"
            }
        })

    print("=== Financial Terminology Corrected! ===")
