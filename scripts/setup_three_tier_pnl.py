"""Setup 3-tier standard financial accounting in Airtable Oylik P&L table:
1. Soliqqacha foyda (Profit Before Tax / EBT)
2. Soliqdan keyingi sof foyda (Profit After Tax / Net Profit)
3. Taqsimlanmagan foyda (Retained Earnings / Zaxira kapitali)
"""
import json
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
PNL_TABLE_ID = "tblUgfwoxSn2fS4wJ"

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
            if t['id'] == PNL_TABLE_ID:
                return {f['name']: f['id'] for f in t.get('fields', [])}
    return {}

def create_field(field_def):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields"
    req = urllib.request.Request(
        url,
        data=json.dumps(field_def).encode('utf-8'),
        headers=HEADERS
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Field '{field_def['name']}' created: HTTP {resp.status}")
    except urllib.error.HTTPError as he:
        print(f"Field '{field_def['name']}' error:", he.read().decode())

def update_pnl_records():
    # Update monthly rows with full tax, dividends and retained earnings
    url = f"https://api.airtable.com/v0/{BASE_ID}/{PNL_TABLE_ID}?maxRecords=10"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    # Sample standard monthly allocations
    allocations = {
        "2026-08": {"tax": 2000000, "dividends": 12000000}, # 4% aylanma soliq ~2M, Dividend 12M -> Retained ~7.5M
        "2026-07": {"tax": 1760000, "dividends": 10000000},
        "2026-06": {"tax": 1520000, "dividends": 8000000},
        "2026-05": {"tax": 1280000, "dividends": 6000000}
    }

    updates = []
    for r in data.get("records", []):
        oy = r["fields"].get("Oy nomi", "")[:7]
        alloc = allocations.get(oy, {"tax": 1500000, "dividends": 8000000})
        updates.append({
            "id": r["id"],
            "fields": {
                "Soliq xarajati (UZS)": alloc["tax"],
                "Taqsimlangan Dividendlar (UZS)": alloc["dividends"]
            }
        })

    if updates:
        patch_url = f"https://api.airtable.com/v0/{BASE_ID}/{PNL_TABLE_ID}"
        patch_req = urllib.request.Request(
            patch_url,
            data=json.dumps({"records": updates}).encode('utf-8'),
            headers=HEADERS,
            method="PATCH"
        )
        with urllib.request.urlopen(patch_req) as resp:
            print(f"Updated P&L records with taxes & dividends: HTTP {resp.status}")

if __name__ == "__main__":
    fields = get_fields()
    print("Found fields in Oylik P&L:", len(fields))

    # 1. Add 'Soliq xarajati (UZS)'
    if "Soliq xarajati (UZS)" not in fields:
        create_field({
            "name": "Soliq xarajati (UZS)",
            "type": "number",
            "options": {"precision": 0}
        })

    # 2. Add 'SOLIQQACHA FOYDA (UZS)' (EBT = Yalpi Foyda - OPEX)
    if "SOLIQQACHA FOYDA (UZS)" not in fields:
        create_field({
            "name": "SOLIQQACHA FOYDA (UZS)",
            "type": "formula",
            "options": {
                "formula": "{Yalpi Foyda (UZS)} - {Operatsion xarajatlar — OPEX (UZS)}"
            }
        })

    # 3. Add 'SOLIQDAN KEYINGI SOF FOYDA (UZS)' (Net Income = Soliqqacha - Soliq)
    if "SOLIQDAN KEYINGI SOF FOYDA (UZS)" not in fields:
        create_field({
            "name": "SOLIQDAN KEYINGI SOF FOYDA (UZS)",
            "type": "formula",
            "options": {
                "formula": "{SOLIQQACHA FOYDA (UZS)} - {Soliq xarajati (UZS)}"
            }
        })

    # 4. Add 'Taqsimlangan Dividendlar (UZS)'
    if "Taqsimlangan Dividendlar (UZS)" not in fields:
        create_field({
            "name": "Taqsimlangan Dividendlar (UZS)",
            "type": "number",
            "options": {"precision": 0}
        })

    # 5. Add 'TAQSIMLANMAGAN FOYDA (UZS)' (Retained Earnings = Soliqdan keyingi - Dividend)
    if "TAQSIMLANMAGAN FOYDA (UZS)" not in fields:
        create_field({
            "name": "TAQSIMLANMAGAN FOYDA (UZS)",
            "type": "formula",
            "options": {
                "formula": "{SOLIQDAN KEYINGI SOF FOYDA (UZS)} - {Taqsimlangan Dividendlar (UZS)}"
            }
        })

    # 6. Add 'Kapital va Zaxira Holati'
    if "Kapital va Zaxira Holati" not in fields:
        create_field({
            "name": "Kapital va Zaxira Holati",
            "type": "formula",
            "options": {
                "formula": "IF({TAQSIMLANMAGAN FOYDA (UZS)} < 0, '🔴 Dividend ko‘p yechilgan (Defitsit)', IF({TAQSIMLANMAGAN FOYDA (UZS)} = 0, '🟡 Zaxirasiz (100% taqsimlandi)', '🟢 Zaxira va o‘sishga qoldi'))"
            }
        })

    update_pnl_records()
