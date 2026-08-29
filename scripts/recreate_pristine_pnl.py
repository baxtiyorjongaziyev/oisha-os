"""Recreate Oylik P&L table from scratch with 100% pure native fields and ZERO arxiv/old fields."""
import os
import urllib.request, json, sys, time

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("AIRTABLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("AIRTABLE_API_KEY is required in the runtime secret configuration")
BASE_ID = "app8xoyx1XCumYFXV"
OLD_PNL_ID = "tblUgfwoxSn2fS4wJ"
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
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as he:
        print("API Error:", he.read().decode())
        raise

def api_patch(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=H, method='PATCH')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as he:
        print("API Patch Error:", he.read().decode())
        raise

# 1. Rename old table
print("1. Renaming old cluttered table...")
api_patch(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{OLD_PNL_ID}", {
    "name": "Arxiv — Eski P&L (Keraksiz)"
})

# 2. Create brand new clean Oylik P&L table
print("2. Creating brand new clean 'Oylik P&L' table...")
new_table_payload = {
    "name": "Oylik P&L",
    "description": "Rasmiy 3 Bosqichli Foyda va Zarar Hisoboti (100% Avtomatik Rollup)",
    "fields": [
        {
            "name": "Oy nomi",
            "type": "singleLineText"
        },
        {
            "name": "Sana",
            "type": "date",
            "options": {"dateFormat": {"name": "iso"}}
        }
    ]
}

new_table = api_post(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables", new_table_payload)
new_pnl_id = new_table["id"]
print(f"Created new Oylik P&L table with ID: {new_pnl_id}")

# 3. Create Link field in Tranzaksiyalar pointing to the new table
print("3. Linking Tranzaksiyalar to new Oylik P&L table...")
link_field_res = api_post(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{TRX_TABLE_ID}/fields", {
    "name": "P&L Oy",
    "type": "multipleRecordLinks",
    "options": {
        "linkedTableId": new_pnl_id
    }
})
print("Link field created in Tranzaksiyalar:", link_field_res.get("name"))

# Refresh schema to get field IDs
tables = api_get(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables").get("tables", [])
new_pnl = next(t for t in tables if t["id"] == new_pnl_id)
new_pnl_fields = {f["name"]: f for f in new_pnl.get("fields", [])}

trx_table = next(t for t in tables if t["id"] == TRX_TABLE_ID)
trx_fields = {f["name"]: f for f in trx_table.get("fields", [])}

link_field_id_in_pnl = new_pnl_fields["Tranzaksiyalar"]["id"]
kirim_uzs_fid = trx_fields["Kirim UZS"]["id"]
chiqim_uzs_fid = trx_fields["Chiqim UZS"]["id"]

# 4. Add native Rollups
print("4. Adding native Rollup fields...")
api_post(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{new_pnl_id}/fields", {
    "name": "Jami Kirim (UZS)",
    "type": "rollup",
    "options": {
        "recordLinkFieldId": link_field_id_in_pnl,
        "fieldIdInLinkedTable": kirim_uzs_fid,
        "formula": "SUM(values)"
    }
})

api_post(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{new_pnl_id}/fields", {
    "name": "Jami Chiqim (UZS)",
    "type": "rollup",
    "options": {
        "recordLinkFieldId": link_field_id_in_pnl,
        "fieldIdInLinkedTable": chiqim_uzs_fid,
        "formula": "SUM(values)"
    }
})

# 5. Add clean formulas
print("5. Adding clean profit chain formulas...")
formulas = [
    ("SOLIQQACHA FOYDA (UZS)", "{Jami Kirim (UZS)} - {Jami Chiqim (UZS)}"),
    ("Soliq xarajati (UZS)", "ROUND({Jami Kirim (UZS)} * 0.04, 0)"),
    ("SOLIQDAN KEYINGI SOF FOYDA (UZS)", "{SOLIQQACHA FOYDA (UZS)} - {Soliq xarajati (UZS)}"),
    ("Taqsimlangan Dividendlar (UZS)", "IF({SOLIQDAN KEYINGI SOF FOYDA (UZS)} > 0, ROUND({SOLIQDAN KEYINGI SOF FOYDA (UZS)} * 0.60, 0), 0)"),
    ("TAQSIMLANMAGAN FOYDA (UZS)", "{SOLIQDAN KEYINGI SOF FOYDA (UZS)} - {Taqsimlangan Dividendlar (UZS)}"),
    ("SOF FOYDA MARJASI (%)", "IF({Jami Kirim (UZS)} > 0, {SOLIQDAN KEYINGI SOF FOYDA (UZS)} / {Jami Kirim (UZS)}, 0)"),
    ("Kapital va Zaxira Holati", "IF({TAQSIMLANMAGAN FOYDA (UZS)} < 0, '🔴 Defitsit', IF({TAQSIMLANMAGAN FOYDA (UZS)} = 0, '🟡 Zaxirasiz (100% taqsimlandi)', '🟢 Zaxira va o‘sishga qoldi'))"),
    ("Oylik Moliyaviy Holat", "IF({SOF FOYDA MARJASI (%)} >= 0.25, '🟢 YUQORI SOF FOYDA (>25%)', IF({SOF FOYDA MARJASI (%)} > 0, '🟡 O‘RTACHA FOYDA', '🔴 ZARARDA'))")
]

for name, formula in formulas:
    api_post(f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{new_pnl_id}/fields", {
        "name": name,
        "type": "formula",
        "options": {"formula": formula}
    })
    print(f"  Created formula: {name}")

# 6. Populate all 35 months (2025-02 through 2027-12)
print("6. Populating all monthly records (2025 - 2027)...")
uzbek_months = {
    "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
    "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
    "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
}

all_months = []
# 2025 months
for m in range(2, 13):
    m_str = f"{m:02d}"
    all_months.append({"fields": {"Oy nomi": f"2025-{m_str} ({uzbek_months[m_str]} 2025)", "Sana": f"2025-{m_str}-01"}})
# 2026 months
for m in range(1, 13):
    m_str = f"{m:02d}"
    all_months.append({"fields": {"Oy nomi": f"2026-{m_str} ({uzbek_months[m_str]} 2026)", "Sana": f"2026-{m_str}-01"}})
# 2027 months
for m in range(1, 13):
    m_str = f"{m:02d}"
    all_months.append({"fields": {"Oy nomi": f"2027-{m_str} ({uzbek_months[m_str]} 2027)", "Sana": f"2027-{m_str}-01"}})

month_id_map = {}
for i in range(0, len(all_months), 10):
    chunk = all_months[i:i+10]
    res = api_post(f"https://api.airtable.com/v0/{BASE_ID}/{new_pnl_id}", {"records": chunk})
    for r in res.get("records", []):
        code = r["fields"].get("Oy nomi", "")[:7]
        month_id_map[code] = r["id"]

print(f"Created {len(month_id_map)} months in new clean table!")

# 7. Link all transactions to the new clean table
print("7. Linking all 335 transactions to the new clean table...")
all_trx = []
offset = None
while True:
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TRX_TABLE_ID}?pageSize=100"
    if offset:
        url += f"&offset={offset}"
    d = api_get(url)
    all_trx.extend(d.get("records", []))
    offset = d.get("offset")
    if not offset:
        break

trx_updates = []
for r in all_trx:
    sana = r["fields"].get("Sana", "")
    if sana and len(sana) >= 7:
        m_code = sana[:7]
        target_id = month_id_map.get(m_code)
        if target_id:
            trx_updates.append({
                "id": r["id"],
                "fields": {
                    "P&L Oy": [target_id]
                }
            })

for i in range(0, len(trx_updates), 10):
    chunk = trx_updates[i:i+10]
    api_patch(f"https://api.airtable.com/v0/{BASE_ID}/{TRX_TABLE_ID}", {"records": chunk})
    time.sleep(0.1)

print(f"Successfully linked {len(trx_updates)} transactions to new Oylik P&L table!")
print(f"NEW CLEAN TABLE ID: {new_pnl_id}")
