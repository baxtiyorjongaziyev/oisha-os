"""Build 100% native Airtable computed fields (Rollups + Formulas) in Oylik P&L.
Eliminates ALL manual editable number fields.
"""
import urllib.request, json, sys, time

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "patADXBB0784iii3w.7c1e4380a9736b30f1dd2cb539f6ac49ac097e3452f84f319dc2060834569fdb"
BASE_ID = "app8xoyx1XCumYFXV"
PNL_TABLE_ID = "tblUgfwoxSn2fS4wJ"
TRX_TABLE_ID = "tblrqxqIzyrvg7XpQ"

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

trx_table = next(t for t in tables if t["id"] == TRX_TABLE_ID)
trx_fields = {f["name"]: f for f in trx_table.get("fields", [])}

link_field_id = pnl_fields["Tranzaksiyalar"]["id"]
kirim_uzs_field_id = trx_fields["Kirim UZS"]["id"]
chiqim_uzs_field_id = trx_fields["Chiqim UZS"]["id"]

# 1. Update/Add Native Rollup fields
def create_or_update_rollup(name, field_id_in_linked):
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields"
    payload = {
        "name": name,
        "type": "rollup",
        "options": {
            "recordLinkFieldId": link_field_id,
            "fieldIdInLinkedTable": field_id_in_linked,
            "formula": "SUM(values)"
        }
    }
    try:
        res = api_post(url, payload)
        print(f"Created Rollup '{name}': {res.get('id')}")
        return res
    except urllib.error.HTTPError as he:
        err = he.read().decode()
        print(f"Error creating '{name}': {err}")

# Create Rollups with clean distinct names if needed, or directly
create_or_update_rollup("JAMI KIRIM (ROLLUP UZS)", kirim_uzs_field_id)
create_or_update_rollup("JAMI CHIQIM (ROLLUP UZS)", chiqim_uzs_field_id)

# 2. Update formulas to use native rollups
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
    if field_info:
        field_id = field_info["id"]
        url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{PNL_TABLE_ID}/fields/{field_id}"
        payload = {
            "name": name,
            "type": "formula",
            "options": {
                "formula": formula
            }
        }
        try:
            api_patch(url, payload)
            print(f"Updated Formula '{name}' -> HTTP 200")
        except urllib.error.HTTPError as he:
            print(f"Error updating formula '{name}': {he.read().decode()}")

print("\nFinished building native Rollup/Formula engine!")
