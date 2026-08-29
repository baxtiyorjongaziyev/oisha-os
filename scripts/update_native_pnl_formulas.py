"""Update formulas to use the native Rollup fields and delete manual number fields in Oylik P&L."""
import os
import urllib.request, json, sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
PNL_TABLE_ID = "tblUgfwoxSn2fS4wJ"

H = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def api_get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def api_post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=H, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def api_patch(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=H, method='PATCH')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

tables = api_get(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables").get("tables", [])
pnl_table = next(t for t in tables if t["id"] == PNL_TABLE_ID)
pnl_fields = {f["name"]: f for f in pnl_table.get("fields", [])}

print("Available P&L fields:")
for f in pnl_table.get("fields", []):
    print(f"  {f['name']} ({f['type']}) -> {f['id']}")

# 1. Update formulas with exact formula payload
formulas = [
    ("SOLIQQACHA FOYDA (UZS)", "{JAMI KIRIM (ROLLUP UZS)} - {JAMI CHIQIM (ROLLUP UZS)}"),
    ("Soliq xarajati (UZS)", "ROUND({JAMI KIRIM (ROLLUP UZS)} * 0.04, 0)"),
    ("SOLIQDAN KEYINGI SOF FOYDA (UZS)", "{SOLIQQACHA FOYDA (UZS)} - {Soliq xarajati (UZS)}"),
    ("Taqsimlangan Dividendlar (UZS)", "IF({SOLIQDAN KEYINGI SOF FOYDA (UZS)} > 0, ROUND({SOLIQDAN KEYINGI SOF FOYDA (UZS)} * 0.60, 0), 0)"),
    ("TAQSIMLANMAGAN FOYDA (UZS)", "{SOLIQDAN KEYINGI SOF FOYDA (UZS)} - {Taqsimlangan Dividendlar (UZS)}"),
    ("SOF FOYDA MARJASI (%)", "IF({JAMI KIRIM (ROLLUP UZS)} > 0, {SOLIQDAN KEYINGI SOF FOYDA (UZS)} / {JAMI KIRIM (ROLLUP UZS)}, 0)")
]

for name, formula in formulas:
    field_info = pnl_fields.get(name)
    if not field_info:
        # Create as new formula field
        url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields"
        payload = {
            "name": name,
            "type": "formula",
            "options": {"formula": formula}
        }
        try:
            res = api_post(url, payload)
            print(f"Created formula '{name}': HTTP 200")
        except urllib.error.HTTPError as he:
            print(f"Error creating formula '{name}':", he.read().decode())
    else:
        # If it was number or formula, update formula options
        field_id = field_info["id"]
        url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields/{field_id}"
        if field_info["type"] == "formula":
            payload = {"options": {"formula": formula}}
        else:
            payload = {"name": name + " (Old)", "description": "Manual backup"}
        try:
            res = api_patch(url, payload)
            print(f"Updated field '{name}': HTTP 200")
            if field_info["type"] != "formula":
                # Create formula version
                create_url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields"
                api_post(create_url, {
                    "name": name,
                    "type": "formula",
                    "options": {"formula": formula}
                })
                print(f"Created new formula '{name}': HTTP 200")
        except urllib.error.HTTPError as he:
            print(f"Error updating field '{name}':", he.read().decode())

print("\nEngine configuration complete!")
