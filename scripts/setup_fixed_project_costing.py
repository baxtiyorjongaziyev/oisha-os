"""Setup Fixed Project Fee Costing for Designers in Airtable Loyihalar table."""
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

def get_fields():
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        for t in data.get('tables', []):
            if t['id'] == TABLE_ID:
                return {f['name']: f['id'] for f in t.get('fields', [])}
    return {}

def create_or_update_field(field_def, existing_fields):
    name = field_def['name']
    if name in existing_fields:
        field_id = existing_fields[name]
        url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields/{field_id}"
        req = urllib.request.Request(
            url,
            data=json.dumps(field_def).encode('utf-8'),
            headers=HEADERS,
            method="PATCH"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"Field '{name}' updated: HTTP {resp.status}")
        except Exception as e:
            print(f"Field '{name}' update info: {e}")
    else:
        url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields"
        req = urllib.request.Request(
            url,
            data=json.dumps(field_def).encode('utf-8'),
            headers=HEADERS
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"Field '{name}' created: HTTP {resp.status}")
        except Exception as e:
            print(f"Field '{name}' create info: {e}")

if __name__ == "__main__":
    fields = get_fields()
    print("Found existing fields:", len(fields))

    # 1. Create 'Dizaynerga kelishilgan to‘lov (UZS)' (Fixed project fee)
    create_or_update_field({
        "name": "Dizaynerga kelishilgan to‘lov (UZS)",
        "type": "number",
        "options": {"precision": 0}
    }, fields)

    # 2. Update 'Haqiqiy ichki tan narx (UZS)' to use fixed project fee or direct expenses
    create_or_update_field({
        "name": "Haqiqiy ichki tan narx (UZS)",
        "type": "formula",
        "options": {
            "formula": "IF({Dizaynerga kelishilgan to‘lov (UZS)} > 0, {Dizaynerga kelishilgan to‘lov (UZS)}, IF({Chiqim — Tranzaksiyalar (UZS)} > 0, {Chiqim — Tranzaksiyalar (UZS)}, 0))"
        }
    }, fields)

    # 3. Update 'Haqiqiy Sof Foyda (UZS)'
    create_or_update_field({
        "name": "Haqiqiy Sof Foyda (UZS)",
        "type": "formula",
        "options": {
            "formula": "{Jami loyiha narxi (UZS)} - {Haqiqiy ichki tan narx (UZS)}"
        }
    }, fields)

    # 4. Update 'Haqiqiy Rentabellik (%)'
    create_or_update_field({
        "name": "Haqiqiy Rentabellik (%)",
        "type": "formula",
        "options": {
            "formula": "IF({Jami loyiha narxi (UZS)} > 0, {Haqiqiy Sof Foyda (UZS)} / {Jami loyiha narxi (UZS)}, 0)"
        }
    }, fields)

    # 5. Update 'Loyiha Rentabellik Holati'
    create_or_update_field({
        "name": "Loyiha Rentabellik Holati",
        "type": "formula",
        "options": {
            "formula": "IF({Haqiqiy Sof Foyda (UZS)} < 0, '🔴 ZARARDA (Minus)', IF({Haqiqiy Rentabellik (%)} < 0.4, '🟡 Past rentabellik (<40%)', '🟢 Yuqori foyda (>50%)'))"
        }
    }, fields)

    print("\n=== Fixed Project Costing Successfully Configured! ===")
